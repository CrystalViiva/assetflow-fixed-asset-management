/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 * AssetFlow Corporate Brand Logo
 */

import React from 'react';

interface AssetFlowLogoProps {
  className?: string;
  size?: number;
}

export const AssetFlowLogo: React.FC<AssetFlowLogoProps> = ({ className = 'h-8 w-auto', size = 32 }) => {
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect width="100" height="100" rx="22" fill="#1e293b" />
      {/* Head circle */}
      <circle cx="50" cy="28" r="7.5" fill="#60a5fa" />
      {/* Left leg of A */}
      <path
        d="M50 35L29 70H39L50 51L61 70H71L50 35Z"
        fill="#38bdf8"
      />
      {/* Crossbar */}
      <path
        d="M34 68H66L61 58H39L34 68Z"
        fill="#2563eb"
      />
      {/* Right Chevron arrow */}
      <path
        d="M68 37.5L82 50L68 62.5"
        stroke="#38bdf8"
        strokeWidth="6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};
