const TOKEN_KEY = "command-center-token";

export function loadToken(): string | null {
	try {
		return localStorage.getItem(TOKEN_KEY);
	} catch {
		return null;
	}
}

export function saveToken(token: string | null) {
	try {
		if (token) localStorage.setItem(TOKEN_KEY, token);
		else localStorage.removeItem(TOKEN_KEY);
	} catch {
		// Storage unavailable (private mode) - token lives in memory only
	}
}

export class ApiError extends Error {
	status: number;

	constructor(message: string, status: number) {
		super(message);
		this.status = status;
	}
}

export async function api<T = unknown>(
	token: string,
	path: string,
	method = "GET",
	body?: unknown,
): Promise<T> {
	const res = await fetch(path, {
		method,
		headers: {
			Authorization: `Bearer ${token}`,
			...(body !== undefined ? { "Content-Type": "application/json" } : {}),
		},
		body: body !== undefined ? JSON.stringify(body) : undefined,
	});
	const data = (await res.json().catch(() => ({}))) as { error?: string };
	if (!res.ok)
		throw new ApiError(
			data.error ?? `Request failed (${res.status})`,
			res.status,
		);
	return data as T;
}
