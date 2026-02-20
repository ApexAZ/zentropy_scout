"use client";

/**
 * Register page — full-screen layout without app shell.
 *
 * REQ-013 §8.3: Email/password registration, OAuth (Google, LinkedIn),
 * real-time password strength indicator, post-registration email
 * confirmation flow.
 *
 * States: idle → submitting → email-sent | error
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

const registerSchema = z
	.object({
		email: z
			.string()
			.min(1, "Email is required")
			.max(254, "Email too long")
			.pipe(z.email("Invalid email format")),
		password: z
			.string()
			.min(1, "Password is required")
			.max(128, "Password too long"),
		confirmPassword: z.string().min(1, "Please confirm your password"),
	})
	.refine((data) => data.password === data.confirmPassword, {
		message: "Passwords do not match",
		path: ["confirmPassword"],
	});

type RegisterFormData = z.infer<typeof registerSchema>;

// ---------------------------------------------------------------------------
// Password strength helpers
// ---------------------------------------------------------------------------

interface PasswordRequirement {
	key: string;
	label: string;
	test: (password: string) => boolean;
}

const PASSWORD_REQUIREMENTS: PasswordRequirement[] = [
	{
		key: "length",
		label: "At least 8 characters",
		test: (p) => p.length >= 8,
	},
	{
		key: "letter",
		label: "At least one letter",
		test: (p) => /[a-zA-Z]/.test(p),
	},
	{
		key: "number",
		label: "At least one number",
		test: (p) => /\d/.test(p),
	},
	{
		key: "special",
		label: "At least one special character",
		test: (p) => /[^a-zA-Z\d]/.test(p),
	},
];

// ---------------------------------------------------------------------------
// View states
// ---------------------------------------------------------------------------

type ViewState = "register" | "email-sent";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RegisterPage() {
	const { status } = useSession();
	const router = useRouter();
	const [view, setView] = useState<ViewState>("register");
	const [error, setError] = useState<string | null>(null);

	// Redirect if already authenticated
	useEffect(() => {
		if (status === "authenticated") {
			router.replace("/");
		}
	}, [status, router]);

	// -----------------------------------------------------------------------
	// Register form
	// -----------------------------------------------------------------------

	const form = useForm<RegisterFormData>({
		resolver: zodResolver(registerSchema),
		defaultValues: { email: "", password: "", confirmPassword: "" },
		mode: "onTouched",
	});

	const watchedPassword = form.watch("password");

	async function onSubmit(data: RegisterFormData) {
		setError(null);
		try {
			await apiPost("/auth/register", {
				email: data.email,
				password: data.password,
			});
			setView("email-sent");
		} catch (err) {
			if (!(err instanceof ApiError)) {
				setError(GENERIC_ERROR);
				return;
			}
			switch (err.status) {
				case 409:
					setError("Email already registered.");
					break;
				case 422:
					setError(
						err.code === "PASSWORD_BREACHED"
							? "This password has appeared in a data breach. Please choose a different one."
							: "Please check your input and try again.",
					);
					break;
				case 400:
					setError("Password does not meet requirements. Please try again.");
					break;
				case 429:
					setError("Too many attempts. Please try again later.");
					break;
				default:
					setError(GENERIC_ERROR);
			}
		}
	}

	// -----------------------------------------------------------------------
	// Render
	// -----------------------------------------------------------------------

	return (
		<main className="bg-muted/40 flex min-h-screen items-center justify-center p-4">
			<Card className="w-full max-w-md">
				<CardHeader className="text-center">
					<CardTitle className="text-2xl">Create Your Account</CardTitle>
					<CardDescription>AI-Powered Job Assistant</CardDescription>
				</CardHeader>

				<CardContent>
					{/* Email sent confirmation */}
					{view === "email-sent" && (
						<div className="space-y-4 text-center">
							<p className="text-muted-foreground text-sm">
								Check your email to verify your account. The link will expire in
								10 minutes.
							</p>
							<Link
								href="/login"
								className="text-primary underline-offset-4 hover:underline"
							>
								Sign in
							</Link>
						</div>
					)}

					{/* Registration form */}
					{view === "register" && (
						<div className="space-y-6">
							{/* OAuth buttons */}
							<div className="space-y-2">
								<Button variant="outline" className="w-full" asChild>
									<a
										href={buildUrl("/auth/providers/google")}
										data-testid="oauth-google"
									>
										Sign up with Google
									</a>
								</Button>
								<Button variant="outline" className="w-full" asChild>
									<a
										href={buildUrl("/auth/providers/linkedin")}
										data-testid="oauth-linkedin"
									>
										Sign up with LinkedIn
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
										or sign up with email
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

							{/* Form */}
							<Form {...form}>
								<form
									onSubmit={form.handleSubmit(onSubmit)}
									className="space-y-4"
								>
									<FormField
										control={form.control}
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
										control={form.control}
										name="password"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Password</FormLabel>
												<FormControl>
													<Input
														type="password"
														placeholder="Create a password"
														autoComplete="new-password"
														{...field}
													/>
												</FormControl>
												<FormMessage />
											</FormItem>
										)}
									/>

									{/* Password strength indicator */}
									<ul
										className="space-y-1 text-xs"
										aria-label="Password requirements"
									>
										{PASSWORD_REQUIREMENTS.map((req) => {
											const met = req.test(watchedPassword);
											return (
												<li
													key={req.key}
													data-testid={`req-${req.key}`}
													data-met={met ? "true" : "false"}
													className={
														met ? "text-green-600" : "text-muted-foreground"
													}
												>
													{met ? "\u2713" : "\u2022"} {req.label}
												</li>
											);
										})}
									</ul>

									<FormField
										control={form.control}
										name="confirmPassword"
										render={({ field }) => (
											<FormItem>
												<FormLabel>Confirm Password</FormLabel>
												<FormControl>
													<Input
														type="password"
														placeholder="Confirm your password"
														autoComplete="new-password"
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
										disabled={form.formState.isSubmitting}
										data-testid="register-submit"
									>
										{form.formState.isSubmitting
											? "Creating account..."
											: "Create Account"}
									</Button>
								</form>
							</Form>

							{/* Sign in link */}
							<p className="text-muted-foreground text-center text-sm">
								Already have an account?{" "}
								<Link
									href="/login"
									className="text-primary underline-offset-4 hover:underline"
								>
									Sign in
								</Link>
							</p>
						</div>
					)}
				</CardContent>
			</Card>
		</main>
	);
}
