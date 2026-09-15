import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "@/App.css";
import "@/workspace.css";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import TeamDashboard from "@/pages/TeamDashboard";
import FinalProtocol from "@/pages/FinalProtocol";
import TeamFinished from "@/pages/TeamFinished";
import OfflineRedeem from "@/pages/OfflineRedeem";
import VolunteerStation from "@/pages/VolunteerStation";
import EventControl from "@/pages/EventControl";
import AdminWorkspace from "@/pages/AdminWorkspace";
import { registerServiceWorker } from "@/lib/offline";

export default function App() {
  useEffect(() => {
    registerServiceWorker();
  }, []);
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/team/login" element={<Login type="team" />} />
        <Route path="/team/dashboard" element={<TeamDashboard />} />
        <Route path="/team/final" element={<FinalProtocol />} />
        <Route path="/team/finished" element={<TeamFinished />} />
        <Route path="/team/redeem" element={<OfflineRedeem />} />
        <Route path="/volunteer/login" element={<Login type="volunteer" />} />
        <Route path="/volunteer/dashboard" element={<VolunteerStation />} />
        <Route path="/admin/login" element={<Login type="admin" />} />
        <Route path="/admin/dashboard" element={<EventControl />} />
        <Route path="/admin/:resource" element={<AdminWorkspace />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}
