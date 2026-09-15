import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Sparkles, Wifi, WifiOff } from "lucide-react";
import { supabase } from "@/lib/supabase";

export function Brand() {
  return (
    <Link className="brand" to="/" data-testid="brand-home-link">
      <span className="brand-mark"><Sparkles size={17} /></span>
      <span>THE LOST PROTOCOL</span>
    </Link>
  );
}

export function StatusPill() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  return (
    <span className={`status-pill ${online ? "online" : "offline"}`} data-testid="network-status">
      {online ? <Wifi size={13} /> : <WifiOff size={13} />} {online ? "LINK ONLINE" : "YOU ARE OFFLINE"}
    </span>
  );
}

export function LivePulse() {
  const [signal, setSignal] = useState("SYNCING");
  useEffect(() => {
    const channel = supabase
      .channel("protocol-live")
      .on("postgres_changes", { event: "*", schema: "public", table: "events" }, () => setSignal("EVENT UPDATED"))
      .on("postgres_changes", { event: "*", schema: "public", table: "announcements" }, () => setSignal("NEW BROADCAST"))
      .on("postgres_changes", { event: "*", schema: "public", table: "team_progress" }, () => setSignal("PROGRESS RECEIVED"))
      .on("postgres_changes", { event: "*", schema: "public", table: "final_attempts" }, () => setSignal("FINAL SUBMISSION"))
      .subscribe((status) => {
        if (status === "SUBSCRIBED") setSignal("LIVE LINK");
      });
    return () => {
      supabase.removeChannel(channel);
    };
  }, []);
  return (
    <span className="live-pulse" data-testid="realtime-status">
      <span className="pulse-dot" /> {signal}
    </span>
  );
}

export function OfflineBanner() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true);
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);
  if (online) return null;
  return (
    <div className="offline-banner" data-testid="offline-banner">
      <WifiOff size={15} /> YOU ARE OFFLINE — your current mission is cached. New submissions require the link to return.
    </div>
  );
}

export default function Shell({ children, role = "MISSION CONTROL" }) {
  return (
    <div className="app-shell">
      <div className="starfield" />
      <header className="topbar">
        <Brand />
        <div className="topbar-right">
          <LivePulse />
          <span className="role-label" data-testid="current-role-label">{role}</span>
          <StatusPill />
        </div>
      </header>
      <OfflineBanner />
      {children}
    </div>
  );
}
