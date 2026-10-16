import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Card({
	title,
	subtitle,
	action,
	children,
}: {
	title: string;
	subtitle?: string;
	action?: ReactNode;
	children: ReactNode;
}) {
	return (
		<section className="rounded-xl bg-white/80 dark:bg-neutral-900/80 backdrop-blur ring-glass shadow-float p-5">
			<div className="flex items-start justify-between gap-3 mb-4">
				<div>
					<h2 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
						{title}
					</h2>
					{subtitle && (
						<p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
							{subtitle}
						</p>
					)}
				</div>
				{action}
			</div>
			{children}
		</section>
	);
}

type Variant = "primary" | "secondary" | "danger" | "ghost";

const variants: Record<Variant, string> = {
	primary:
		"bg-neutral-900 text-white hover:bg-neutral-700 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200",
	secondary:
		"bg-neutral-100 text-neutral-800 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-100 dark:hover:bg-neutral-700",
	danger: "bg-red-600 text-white hover:bg-red-500",
	ghost:
		"text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800",
};

export function Button({
	variant = "primary",
	className = "",
	...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
	return (
		<button
			{...props}
			className={`inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${className}`}
		/>
	);
}

export const inputClass =
	"w-full rounded-lg border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-950 px-3 py-2 text-sm text-neutral-900 dark:text-neutral-100 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-orange-400/60";

export function Toggle({
	checked,
	onChange,
	label,
	disabled,
}: {
	checked: boolean;
	onChange: (value: boolean) => void;
	label: string;
	disabled?: boolean;
}) {
	return (
		<label className="inline-flex items-center gap-2 text-xs text-neutral-600 dark:text-neutral-300 cursor-pointer select-none">
			<button
				type="button"
				role="switch"
				aria-checked={checked}
				disabled={disabled}
				onClick={() => onChange(!checked)}
				className={`relative h-5 w-9 rounded-full transition-colors disabled:opacity-40 ${checked ? "bg-emerald-500" : "bg-neutral-300 dark:bg-neutral-700"}`}
			>
				<span
					className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-4" : ""}`}
				/>
			</button>
			{label}
		</label>
	);
}
