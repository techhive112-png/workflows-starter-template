/**
 * Owner-only access. Every API call must carry the OWNER_TOKEN secret:
 *   Authorization: Bearer <OWNER_TOKEN>
 *
 * If OWNER_TOKEN is not configured, nothing is allowed (fail closed).
 */

export const MIN_TOKEN_LENGTH = 16;

export type AuthResult =
	| { ok: true }
	| { ok: false; status: 401 | 503; error: string };

export function checkOwner(request: Request, env: Env): AuthResult {
	const expected = env.OWNER_TOKEN;
	if (!expected || expected.length < MIN_TOKEN_LENGTH) {
		return {
			ok: false,
			status: 503,
			error: `OWNER_TOKEN is not set (or shorter than ${MIN_TOKEN_LENGTH} characters). The Command Center is locked.`,
		};
	}

	const header = request.headers.get("Authorization") ?? "";
	const provided = header.startsWith("Bearer ") ? header.slice(7) : "";

	if (!timingSafeEqual(provided, expected)) {
		return { ok: false, status: 401, error: "Not the owner." };
	}
	return { ok: true };
}

function timingSafeEqual(a: string, b: string): boolean {
	const enc = new TextEncoder();
	const left = enc.encode(a);
	const right = enc.encode(b);
	if (left.byteLength !== right.byteLength) {
		// Still do a comparison so timing does not reveal the length difference.
		crypto.subtle.timingSafeEqual(right, right);
		return false;
	}
	return crypto.subtle.timingSafeEqual(left, right);
}
