import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { IphoneFrame } from "./screens/IphoneFrame";

createRoot(document.getElementById("app")).render(
  <StrictMode>
    <IphoneFrame />
  </StrictMode>,
);
