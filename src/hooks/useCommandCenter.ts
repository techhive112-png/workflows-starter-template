import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { CommandCenterState } from "../types";

interface LiveState {
	state: CommandCenterState | null;
	connected: boolean;
	unauthorized: boolean;
}

/**
 * Keeps the dashboard in sync with the Command Center over a WebSocket.
 * Each connection uses a fresh one-time ticket obtained with the owner token.
 */
export function useCommandCenter(token: string): LiveState {
	const [live, setLive] = useState<LiveState>({
		state: null,
		connected: false,
		unauthorized: false,
	});

	useEffect(() => {
		let ws: WebSocket | null = null;
		let retry: ReturnType<typeof setTimeout> | undefined;
		let stopped = false;

		const connect = async () => {
			try {
				const { ticket } = await api<{ ticket: string }>(
					token,
					"/api/ws-ticket",
					"POST",
				);
				if (stopped) return;
				const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
				ws = new WebSocket(
					`${protocol}//${window.location.host}/ws?ticket=${ticket}`,
				);
				ws.onopen = () => setLive((l) => ({ ...l, connected: true }));
				ws.onmessage = (event) => {
					try {
						const msg = JSON.parse(event.data);
						if (msg.type === "state")
							setLive((l) => ({ ...l, state: msg.state }));
					} catch {
						// Ignore malformed messages
					}
				};
				ws.onclose = () => {
					setLive((l) => ({ ...l, connected: false }));
					if (!stopped) retry = setTimeout(connect, 2000);
				};
			} catch (err) {
				if (
					err instanceof ApiError &&
					(err.status === 401 || err.status === 503)
				) {
					setLive((l) => ({ ...l, unauthorized: true }));
					return;
				}
				if (!stopped) retry = setTimeout(connect, 3000);
			}
		};

		connect();
		return () => {
			stopped = true;
			clearTimeout(retry);
			ws?.close();
		};
	}, [token]);

	return live;
}
