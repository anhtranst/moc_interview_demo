export interface TokenResponse {
  token: string;
  livekit_url: string;
  room_name: string;
}

export async function fetchToken(
  participantName: string,
  roomName?: string
): Promise<TokenResponse> {
  const res = await fetch("/api/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_name: participantName,
      room_name: roomName ?? "",
    }),
  });

  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Token request failed: ${detail}`);
  }

  return res.json();
}
