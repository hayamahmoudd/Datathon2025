import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Image from "next/image";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "ShelterMap Toronto",
  description: "Where need meets direction.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <Image
          src="/logo.png"
          alt="ShelterMap Toronto Logo"
          width={80}
          height={80}
          className="fixed top-4 left-4 z-50"
          priority
        />
        {children}
      </body>
    </html>
  );
}
