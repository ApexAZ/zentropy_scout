import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

const nextConfig: NextConfig = {
	poweredByHeader: false,
	async headers() {
		return [
			{
				source: "/(.*)",
				headers: [
					{
						key: "X-Frame-Options",
						value: "DENY",
					},
					{
						key: "X-Content-Type-Options",
						value: "nosniff",
					},
					{
						key: "Referrer-Policy",
						value: "strict-origin-when-cross-origin",
					},
					{
						key: "Permissions-Policy",
						value: "camera=(), microphone=(), geolocation=()",
					},
					{
						// Disabled (0) because the CSP is the proper XSS protection.
						// The XSS Auditor was removed from all modern browsers and
						// mode=block can introduce vulnerabilities on older IE versions.
						key: "X-XSS-Protection",
						value: "0",
					},
					{
						// Browsers ignore HSTS on localhost, so this is safe to
						// include unconditionally and activates when deployed over HTTPS.
						key: "Strict-Transport-Security",
						value: "max-age=31536000; includeSubDomains",
					},
					{
						// CSP for frontend app. unsafe-inline is required because Next.js
						// injects inline <script> tags for hydration data (__NEXT_DATA__).
						// unsafe-eval is dev-only (Fast Refresh/HMR) and stripped in production.
						// Production hardening: replace unsafe-inline with nonce-based CSP
						// via Next.js middleware (requires per-request nonce generation).
						key: "Content-Security-Policy",
						value: [
							"default-src 'self'",
							`script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
							"style-src 'self' 'unsafe-inline'",
							"img-src 'self' data: blob:",
							"font-src 'self'",
							isDev
								? "connect-src 'self' http://localhost:* ws://localhost:*"
								: "connect-src 'self'",
							"frame-ancestors 'none'",
							"base-uri 'self'",
							"form-action 'self'",
							"object-src 'none'",
						].join("; "),
					},
				],
			},
		];
	},
};

export default nextConfig;
