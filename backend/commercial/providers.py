"""Payment transport only; browser outcomes never grant entitlements."""

import hashlib
import hmac
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import ValidationError

from commercial.models import Checkout, ProviderPlan


class LocalSandboxProvider:
    name = "local_sandbox"

    def secret(self):
        return salted_hmac("assetflow.local-sandbox.webhooks", "v1", algorithm="sha256").hexdigest()

    def signature(self, body):
        return hmac.new(self.secret().encode(), body, hashlib.sha512).hexdigest()

    def verify_signature(self, body, signature):
        return (
            isinstance(signature, str)
            and len(signature) == 128
            and all(char in "0123456789abcdefABCDEF" for char in signature)
            and hmac.compare_digest(self.signature(body), signature.lower())
        )

    def initialize(self, checkout, email):
        return f"#billing?checkout={checkout.id}"

    def verify(self, reference):
        checkout = Checkout.objects.get(provider_reference=reference, provider=self.name)
        return {
            "reference": reference,
            "status": checkout.sandbox_status,
            "amount_minor": checkout.amount_minor,
            "currency": checkout.currency,
            "occurred_at": checkout.sandbox_updated_at,
            "customer": f"sandbox-{checkout.organization_id}",
        }


class PaystackTestProvider(LocalSandboxProvider):
    name = "paystack_test"

    def secret(self):
        if not settings.PAYSTACK_SECRET_KEY.startswith("sk_test_"):
            raise ValidationError("A Paystack test key must be configured.")
        return settings.PAYSTACK_SECRET_KEY

    def request(self, path, data=None, *, empty=False):
        request = Request(
            f"https://api.paystack.co{path}",
            data=json.dumps(data).encode() if data is not None else None,
            headers={
                "Authorization": f"Bearer {self.secret()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read(1_000_000))
        if result.get("status") is not True:
            raise ValidationError("The payment provider could not confirm this request.")
        if empty:
            return {}
        if not isinstance(result.get("data"), dict):
            raise ValidationError("The payment provider returned an invalid record.")
        return result["data"]

    def check_plan(self, plan, code):
        data = self.request(f"/plan/{quote(code, safe='')}")
        if (
            data.get("domain") != "test"
            or data.get("plan_code") != code
            or data.get("amount") != int(plan.monthly_amount * 100)
            or data.get("currency") != plan.currency
            or data.get("interval") != "monthly"
            or data.get("invoice_limit") not in (None, 0)
        ):
            raise ValidationError("Provider plan does not match these monthly sandbox terms.")

    def initialize(self, checkout, email):
        mapping = ProviderPlan.objects.filter(plan=checkout.plan).first()
        if not mapping:
            raise ValidationError(
                "An operator must map this plan to a verified Paystack test plan."
            )
        self.check_plan(checkout.plan, mapping.code)
        data = self.request(
            "/transaction/initialize",
            {
                "email": email,
                "amount": checkout.amount_minor,
                "currency": checkout.currency,
                "reference": checkout.provider_reference,
                "plan": mapping.code,
                "channels": ["card"],
                "callback_url": settings.FRONTEND_BASE_URL.rstrip("/") + "/#billing",
            },
        )
        url = data.get("authorization_url", "")
        if not url.startswith("https://checkout.paystack.com/"):
            raise ValidationError("Unexpected provider checkout address.")
        return url

    def verify(self, reference):
        from django.utils.dateparse import parse_datetime

        data = self.request(f"/transaction/verify/{quote(reference, safe='')}")
        if data.get("domain") != "test":
            raise ValidationError("Only sandbox transactions are supported.")
        return {
            "reference": data.get("reference"),
            "status": {"success": "SUCCEEDED", "failed": "FAILED", "reversed": "REFUNDED"}.get(
                data.get("status"), "PENDING"
            ),
            "amount_minor": data.get("amount"),
            "currency": data.get("currency"),
            "occurred_at": parse_datetime(data.get("paid_at") or data.get("created_at") or ""),
            "customer": str(data.get("customer", {}).get("customer_code", "")),
            "email": data.get("customer", {}).get("email", ""),
            "plan": (data.get("plan_object") or {}).get("plan_code")
            or (
                data.get("plan", {}).get("plan_code")
                if isinstance(data.get("plan"), dict)
                else data.get("plan")
            ),
        }

    def subscription(self, code):
        data = self.request(f"/subscription/{quote(code, safe='')}")
        if data.get("domain") != "test" or data.get("subscription_code") != code:
            raise ValidationError("Provider subscription is not a matching test subscription.")
        return data

    def disable(self, code):
        data = self.subscription(code)
        if data.get("status") in {"non-renewing", "cancelled", "completed", "complete"}:
            return
        token = data.get("email_token")
        if not isinstance(token, str) or not token:
            raise ValidationError("Provider cancellation token is unavailable.")
        self.request("/subscription/disable", {"code": code, "token": token}, empty=True)
        # The token is used in memory only, never persisted or returned to a browser.


def provider(name=None):
    selected = name or settings.BILLING_PROVIDER
    if selected != settings.BILLING_PROVIDER or selected not in {"local_sandbox", "paystack_test"}:
        raise ValidationError("Sandbox billing is not configured for this environment.")
    return LocalSandboxProvider() if selected == "local_sandbox" else PaystackTestProvider()
