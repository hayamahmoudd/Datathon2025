"use client";


import dynamic from "next/dynamic";

const TorontoMap = dynamic(() => import("./toronto-map"), { ssr: false });

export default function Page() {
  return (
    <main style={{ height: "100vh", width: "100%" }}>
      <TorontoMap />
    </main>
  );
}