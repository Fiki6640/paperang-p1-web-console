import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router";
import { Toast } from "@heroui/react";
import "./index.css";
import Layout from "./app/Layout";
import { StatusProvider } from "./lib/status";
import Home from "./pages/Home";
import TextPrint from "./pages/TextPrint";
import ImagePrint from "./pages/ImagePrint";
import Weather from "./pages/Weather";
import TempChart from "./pages/TempChart";
import Settings from "./pages/Settings";

// 注意:
// 1. HeroUI v3 的 Toast.Provider 是 toast 堆叠区域(不是应用包裹器),
//    必须与应用内容平级,toast.* 从共享队列推送、由该区域渲染。
// 2. react-router v8 的 useBlocker 等数据 API 要求 createBrowserRouter,
//    不能用 BrowserRouter。
const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/text-print", element: <TextPrint /> },
      { path: "/image-print", element: <ImagePrint /> },
      { path: "/weather", element: <Weather /> },
      { path: "/temp-chart", element: <TempChart /> },
      { path: "/settings", element: <Settings /> },
      { path: "*", element: <Home /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StatusProvider>
      <RouterProvider router={router} />
      <Toast.Provider placement="top end" />
    </StatusProvider>
  </StrictMode>,
);
