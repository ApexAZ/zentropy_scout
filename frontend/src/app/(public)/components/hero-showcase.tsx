/**
 * @fileoverview Hero section rotating feature showcase.
 *
 * Layer: component
 * Feature: shared
 *
 * REQ-024 §4.2: Auto-cycling visual demos of the 4 main features,
 * fading in/out on the hero's right side. No outer border — content
 * floats on the page background.
 *
 * Coordinates with:
 * - app/(public)/components/hero-section.tsx: hero layout
 *
 * Called by / Used by:
 * - app/(public)/components/hero-section.tsx: right-side showcase slot
 */

"use client";

import { useEffect, useState } from "react";

import { BarChart3, FileText, Search, UserCircle } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Mockup content
// ---------------------------------------------------------------------------

function PersonaMockup() {
	return (
		<div className="space-y-5">
			<div className="flex items-center gap-4">
				<div className="bg-primary/20 h-16 w-16 rounded-full" />
				<div className="space-y-2">
					<div className="bg-foreground/20 h-4 w-36 rounded" />
					<div className="bg-foreground/10 h-3 w-24 rounded" />
				</div>
			</div>
			<div className="flex flex-wrap gap-2">
				{[
					"React",
					"TypeScript",
					"Python",
					"Leadership",
					"AWS",
					"Node.js",
					"SQL",
				].map((skill) => (
					<span
						key={skill}
						className="bg-primary/10 text-primary rounded-full px-3 py-1 text-xs"
					>
						{skill}
					</span>
				))}
			</div>
			<div className="space-y-3">
				<p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
					Experience
				</p>
				{[
					{ title: "w-40", company: "w-28", date: "w-20" },
					{ title: "w-36", company: "w-24", date: "w-16" },
					{ title: "w-44", company: "w-32", date: "w-20" },
				].map((widths, i) => (
					<div key={i} className="space-y-1.5">
						<div className={`bg-foreground/20 h-3 rounded ${widths.title}`} />
						<div className="flex gap-3">
							<div
								className={`bg-foreground/10 h-2.5 rounded ${widths.company}`}
							/>
							<div
								className={`bg-foreground/10 h-2.5 rounded ${widths.date}`}
							/>
						</div>
					</div>
				))}
			</div>
		</div>
	);
}

function JobMatchingMockup() {
	const jobs = [
		{
			title: "Senior Engineer",
			company: "Acme Corp",
			match: 94,
			matchClass: "text-success",
		},
		{
			title: "Frontend Lead",
			company: "Startup Inc",
			match: 87,
			matchClass: "text-primary",
		},
		{
			title: "Full Stack Dev",
			company: "TechCo",
			match: 72,
			matchClass: "text-muted-foreground",
		},
		{
			title: "Backend Engineer",
			company: "DataCo",
			match: 68,
			matchClass: "text-muted-foreground",
		},
		{
			title: "DevOps Lead",
			company: "InfraTech",
			match: 61,
			matchClass: "text-muted-foreground",
		},
	];
	return (
		<div className="space-y-3">
			{jobs.map((job) => (
				<div
					key={job.title}
					className="bg-card/60 flex items-center justify-between rounded-lg px-4 py-3"
				>
					<div>
						<p className="text-foreground text-sm font-medium">{job.title}</p>
						<p className="text-muted-foreground text-xs">{job.company}</p>
					</div>
					<span className={cn("text-sm font-semibold", job.matchClass)}>
						{job.match}%
					</span>
				</div>
			))}
		</div>
	);
}

function DocumentsMockup() {
	return (
		<div className="bg-card/60 space-y-4 rounded-lg px-6 py-5">
			<div className="space-y-1.5">
				<div className="bg-foreground/20 h-4 w-40 rounded" />
				<div className="bg-foreground/10 h-3 w-28 rounded" />
			</div>
			<div className="space-y-2">
				<p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
					Experience
				</p>
				<div className="bg-primary/30 h-2.5 w-full rounded" />
				<div className="bg-foreground/10 h-2.5 w-5/6 rounded" />
				<div className="bg-primary/20 h-2.5 w-4/6 rounded" />
			</div>
			<div className="space-y-2">
				<p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
					Skills
				</p>
				<div className="flex flex-wrap gap-1.5">
					{["w-12", "w-16", "w-10", "w-14", "w-12", "w-16"].map((w, i) => (
						<div key={i} className={`bg-primary/20 h-5 rounded-full ${w}`} />
					))}
				</div>
			</div>
			<div className="space-y-2">
				<p className="text-muted-foreground text-xs font-semibold tracking-wide uppercase">
					Education
				</p>
				<div className="bg-foreground/10 h-2.5 w-full rounded" />
				<div className="bg-foreground/10 h-2.5 w-3/4 rounded" />
			</div>
		</div>
	);
}

function ApplicationsMockup() {
	const apps = [
		{
			title: "Product Designer",
			company: "DesignCo",
			status: "Interview",
			statusClass: "bg-amber-500/20 text-amber-600",
		},
		{
			title: "UX Lead",
			company: "BigTech",
			status: "Applied",
			statusClass: "bg-muted text-muted-foreground",
		},
		{
			title: "Sr. Engineer",
			company: "StartupXYZ",
			status: "Offer",
			statusClass: "bg-success/20 text-success",
		},
		{
			title: "Dev Advocate",
			company: "OpenSource",
			status: "Applied",
			statusClass: "bg-muted text-muted-foreground",
		},
		{
			title: "Data Analyst",
			company: "Analytics Inc",
			status: "Rejected",
			statusClass: "bg-destructive/20 text-destructive",
		},
	];
	return (
		<div className="space-y-2">
			{apps.map((app) => (
				<div
					key={app.title}
					className="bg-card/60 flex items-center justify-between rounded-lg px-4 py-2.5"
				>
					<div>
						<p className="text-foreground text-sm font-medium">{app.title}</p>
						<p className="text-muted-foreground text-xs">{app.company}</p>
					</div>
					<span
						className={cn(
							"rounded-full px-2.5 py-0.5 text-xs font-medium",
							app.statusClass,
						)}
					>
						{app.status}
					</span>
				</div>
			))}
		</div>
	);
}

// ---------------------------------------------------------------------------
// Slide data
// ---------------------------------------------------------------------------

interface Slide {
	icon: LucideIcon;
	title: string;
	content: React.ReactNode;
}

const SLIDES: Slide[] = [
	{
		icon: UserCircle,
		title: "Build Your Persona",
		content: <PersonaMockup />,
	},
	{
		icon: Search,
		title: "Smart Job Matching",
		content: <JobMatchingMockup />,
	},
	{
		icon: FileText,
		title: "Tailored Documents",
		content: <DocumentsMockup />,
	},
	{
		icon: BarChart3,
		title: "Track Applications",
		content: <ApplicationsMockup />,
	},
];

const SLIDE_INTERVAL_MS = 3500;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function HeroShowcase() {
	const [activeIndex, setActiveIndex] = useState(0);

	useEffect(() => {
		const timer = setInterval(() => {
			setActiveIndex((prev) => (prev + 1) % SLIDES.length);
		}, SLIDE_INTERVAL_MS);
		return () => clearInterval(timer);
	}, []);

	return (
		<div
			data-testid="hero-showcase"
			className="relative h-80 w-full lg:h-[600px]"
		>
			{SLIDES.map((slide, index) => {
				const Icon = slide.icon;
				return (
					<div
						key={slide.title}
						className={cn(
							"absolute inset-0 transition-opacity duration-1000",
							activeIndex === index
								? "opacity-100"
								: "pointer-events-none opacity-0",
						)}
					>
						<div className="mb-5 flex items-center gap-3">
							<Icon className="text-primary h-6 w-6" />
							<h3 className="text-foreground text-lg font-semibold">
								{slide.title}
							</h3>
						</div>
						{slide.content}
					</div>
				);
			})}
		</div>
	);
}
