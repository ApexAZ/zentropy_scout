/**
 * @fileoverview Tailwind CSS class-name merge utility (cn function).
 *
 * Layer: lib/utility
 * Feature: shared
 *
 * Combines clsx conditional class-names with tailwind-merge conflict
 * resolution. Used by virtually every UI component in the project.
 *
 * Coordinates with:
 * - app/globals.css: theme tokens and CSS custom properties resolved by twMerge
 *
 * Called by / Used by:
 * - components/ui/*: all shadcn primitives import cn() for class merging
 * - components/*: ~62 UI components across all feature domains
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
