import { supabase } from "@/lib/supabase";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const NODES = ["A", "B", "C", "D", "E", "F", "G"];

export function formatDetail(detail) {
  if (!detail) return "Action rejected.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join(" ");
  }
  return detail.msg || String(detail);
}

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(formatDetail(body.detail) || "Request failed");
  }

  return body;
}

export async function authorizedRequest(path, method = "GET", payload = {}) {
  const { data } = await supabase.auth.getSession();
  const access_token = data.session?.access_token;

  if (!access_token) {
    throw new Error("AUTH REQUIRED — sign in as an operator to continue.");
  }

  if (method === "GET") {
    return apiRequest(path, {
      headers: {
        Authorization: `Bearer ${access_token}`,
      },
    });
  }

  if (method === "DELETE") {
    const response = await fetch(`${API}${path}`, {
      method: "DELETE",
      headers: {
        Authorization: `Bearer ${access_token}`,
      },
    });

    const body = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(formatDetail(body.detail) || "Request failed");
    }

    return body;
  }

  return apiRequest(path, {
    method,
    body: JSON.stringify({
      access_token,
      ...payload,
    }),
  });
}

export function getTeamSession() {
  try {
    return JSON.parse(sessionStorage.getItem("lp_team") || "null");
  } catch {
    return null;
  }
}

export function saveTeamSession(session) {
  sessionStorage.setItem("lp_team", JSON.stringify(session));
}

export function clearTeamSession() {
  sessionStorage.removeItem("lp_team");
}