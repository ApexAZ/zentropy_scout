/**
 * Tailwind CSS class-name merge utility.
 *
 * Combines clsx conditional class-names with tailwind-merge conflict
 * resolution. Used by virtually every UI component in the project.
 *
 * @module lib/utils
 * @coordinates-with components/ui/* (all shadcn primitives import cn()),
 *   app/globals.css (theme tokens resolved by twMerge)
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}
