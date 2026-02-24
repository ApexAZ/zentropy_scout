"use client";

/**
 * Login page — full-screen layout without app shell.
 *
 * REQ-013 §8.2: Email/password login, OAuth (Google, LinkedIn),
 * forgot password via magic link, post-auth redirect.
 *
 * States: idle → submitting → redirect | error
 * Magic link sub-states: idle → sending → magic-link-sent | error
 */

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { ApiError, apiPost, buildUrl } from "@/lib/api-client";
import { useSession } from "@/lib/auth-provider";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GENERIC_ERROR = "Something went wrong. Please try again.";

// ---------------------------------------------------------------------------
// Schemas
// ---------------------------------------------------------------------------

const emailField = z
	.string()
	.min(1, "Email is required")
	.max(254, "Email too long")
	.pipe(z.email("Invalid email format"));

const loginSchema = z.object({
	email: emailField,
	password: z
		.string()
		.min(1, "Password is required")
		.max(128, "Password too long"),
});

type LoginFormData = z.infer<typeof loginSchema>;

const magicLinkSchema = z.object({
	email: emailField,
});

type MagicLinkFormData = z.infer<typeof magicLinkSchema>;

// ---------------------------------------------------------------------------
// View states
// ---------------------------------------------------------------------------

type ViewState = "login" | "forgot-password" | "magic-link-sent";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function LoginPage() {
	const { status } = useSession();
	const router = useRouter();
	const [view, setView] = useState<ViewState>("login");
	const [error, setError] = useState<string | null>(null);

	// Redirect if already authenticated (skip when waiting for magic link —
	// the link opens in a new tab, so this tab should stay put)
	useEffect(() => {
		if (status === "authenticated" && view !== "magic-link-sent") {
			router.replace("/");
		}
	}, [status, router, view]);

	// -----------------------------------------------------------------------
	// Login form
	// -----------------------------------------------------------------------

	const loginForm = useForm<LoginFormData>({
		resolver: zodResolver(loginSchema),
		defaultValues: { email: "", password: "" },
		mode: "onTouched",
	});

	async function onLoginSubmit(data: LoginFormData) {
		setError(null);
		try {
			await apiPost("/auth/verify-password", {
				email: data.email,
				password: data.password,
			});
			// Full page load (not client-side nav) so AuthProvider remounts
			// and calls /auth/me with the new cookie
			window.location.assign("/");
		} catch (err) {
			if (!(err instanceof ApiError)) {
				setError(GENERIC_ERROR);
			} else if (err.status === 401) {
				setError("Invalid email or password.");
			} else if (err.status === 403 && err.code === "EMAIL_NOT_VERIFIED") {
				setError("Please verify your email before signing in.");
			} else if (err.status === 429) {
				setError("Too many attempts. Please try again later.");
			} else {
				setError(GENERIC_ERROR);
			}
		}
	}

	// -----------------------------------------------------------------------
	// Magic link form
	// -----------------------------------------------------------------------

	const magicLinkForm = useForm<MagicLinkFormData>({
		resolver: zodResolver(magicLinkSchema),
		defaultValues: { email: "" },
		mode: "onTouched",
	});

	async function onMagicLinkSubmit(data: MagicLinkFormData) {
		setError(null);
		try {
			await apiPost("/auth/magic-link", {
				email: data.email,
				purpose: "password_reset",
			});
			setView("magic-link-sent");
		} catch {
			setError(GENERIC_ERROR);
		}
	}

	function handleBackToLogin() {
		setView("login");
		setError(null);
		magicLinkForm.reset();
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<main className="bg-muted/40 flex min-h-screen items-center justify-center p-4">
			<Card className="w-full max-w-md">
				<CardHeader className="text-center">
					<CardTitle className="text-2xl">Sign in to Zentropy Scout</CardTitle>
					<CardDescription>AI-Powered Job Assistant</CardDescription>
				</CardHeader>

				<CardContent>
					{/* Magic link sent confirmation */}
					{view === "magic-link-sent" && (
						<div className="space-y-4 text-center">
							<p className="text-muted-foreground text-sm">
								Check your email for a sign-in link. It will expire in 10
								minutes.
							</p>
							<p className="text-muted-foreground text-xs">
								The link will open in a new tab. You can close this tab after
								clicking it.
							</p>
							<Button variant="ghost" onClick={handleBackToLogin}>
								Back to sign in
							</Button>
						</div>
					)}

					{/* Login or Forgot Password form */}
					{view !== "magic-link-sent" && (
						<div className="space-y-6">
							{/* OAuth buttons */}
							<div className="space-y-2">
								<Button variant="outline" className="w-full" asChild>
									<a
										href={buildUrl("/auth/providers/google")}
										data-testid="oauth-google"
									>
										Sign in with Google
									</a>
								</Button>
								<Button variant="outline" className="w-full" asChild>
									<a
										href={buildUrl("/auth/providers/linkedin")}
										data-testid="oauth-linkedin"
									>
										Sign in with LinkedIn
									</a>
								</Button>
							</div>

							{/* Divider */}
							<div className="relative">
								<div className="absolute inset-0 flex items-center">
									<span className="w-full border-t" />
								</div>
								<div className="relative flex justify-center text-xs uppercase">
									<span className="bg-card text-muted-foreground px-2">
										or sign in with email
									</span>
								</div>
							</div>

							{/* Error message */}
							{error && (
								<p
									className="text-destructive text-sm"
									data-testid="submit-error"
									role="alert"
								>
									{error}
								</p>
							)}

							{/* Login form */}
							{view === "login" && (
								<Form {...loginForm}>
									<form
										onSubmit={loginForm.handleSubmit(onLoginSubmit)}
										className="space-y-4"
									>
										<FormField
											control={loginForm.control}
											name="email"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Email</FormLabel>
													<FormControl>
														<Input
															type="email"
															placeholder="you@example.com"
															autoComplete="email"
															{...field}
														/>
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<FormField
											control={loginForm.control}
											name="password"
											render={({ field }) => (
												<FormItem>
													<FormLabel>Password</FormLabel>
													<FormControl>
														<Input
															type="password"
															placeholder="Enter your password"
															autoComplete="current-password"
															{...field}
														/>
													</FormControl>
													<FormMessage />
												</FormItem>
											)}
										/>

										<div className="flex justify-end">
											<Button
												type="button"
												variant="link"
												className="h-auto p-0 text-sm"
												onClick={() => {
													setView("forgot-password");
													setError(null);
												}}
											>
												Forgot password?
											</Button>
										</div>

										<Button
											type="submit"
											className="w-full"
											disabled={loginForm.formState.isSubmitting}
											data-testid="login-submit"
										>
											{loginForm.formState.isSubmitting
												? "Signing in..."
												: "Sign In"}
										</Button>
									</form>
								</Form>
							)}

							{/* Forgot password form */}
							{view === "forgot-password" && (
								<div className="space-y-4">
									<p className="text-muted-foreground text-sm">
										Enter your email and we&apos;ll send a sign-in link to your
										inbox.
									</p>

									<Form {...magicLinkForm}>
										<form
											onSubmit={magicLinkForm.handleSubmit(onMagicLinkSubmit)}
											className="space-y-4"
										>
											<FormField
												control={magicLinkForm.control}
												name="email"
												render={({ field }) => (
													<FormItem>
														<FormLabel>Email</FormLabel>
														<FormControl>
															<Input
																type="email"
																placeholder="you@example.com"
																autoComplete="email"
																{...field}
															/>
														</FormControl>
														<FormMessage />
													</FormItem>
												)}
											/>

											<Button
												type="submit"
												className="w-full"
												disabled={magicLinkForm.formState.isSubmitting}
												data-testid="magic-link-submit"
											>
												{magicLinkForm.formState.isSubmitting
													? "Sending..."
													: "Send sign-in link"}
											</Button>
										</form>
									</Form>

									<div className="text-center">
										<Button variant="ghost" onClick={handleBackToLogin}>
											Back to sign in
										</Button>
									</div>
								</div>
							)}

							{/* Create account link */}
							<p className="text-muted-foreground text-center text-sm">
								Don&apos;t have an account?{" "}
								<Link
									href="/register"
									className="text-primary underline-offset-4 hover:underline"
								>
									Create account
								</Link>
							</p>
						</div>
					)}
				</CardContent>
			</Card>
		</main>
	);
}
