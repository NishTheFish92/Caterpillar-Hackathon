import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Safety from "./pages/Safety.jsx";
import Training from "./pages/Training.jsx";
import Behavior from "./pages/Behavior.jsx";
import Estimation from "./pages/Estimation.jsx";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="safety" element={<Safety />} />
        <Route path="training" element={<Training />} />
        <Route path="behavior" element={<Behavior />} />
        <Route path="estimation" element={<Estimation />} />
      </Route>
    </Routes>
  );
}
