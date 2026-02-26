export interface TokenResponse {
  token: string;
  livekit_url: string;
  room_name: string;
  interview_code: string;
}

export async function fetchToken(
  participantName: string,
  interviewCode: string,
  roomName?: string
): Promise<TokenResponse> {
  const res = await fetch("/api/token", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      participant_name: participantName,
      interview_code: interviewCode,
      room_name: roomName ?? "",
    }),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ?? `Request failed (${res.status})`;
    throw new Error(detail);
  }

  return res.json();
}
