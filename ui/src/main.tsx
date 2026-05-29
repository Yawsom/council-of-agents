import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { RunSessionProvider } from "@/context/RunSessionContext";
import { App } from "@/App";
import { GraphView } from "@/views/GraphView";
import { ChatView } from "@/views/ChatView";
import "@/styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <RunSessionProvider>
        <Routes>
          <Route path="/" element={<App />}>
            <Route index element={<GraphView />} />
            <Route path="chat" element={<ChatView />} />
          </Route>
        </Routes>
      </RunSessionProvider>
    </BrowserRouter>
  </StrictMode>
);
