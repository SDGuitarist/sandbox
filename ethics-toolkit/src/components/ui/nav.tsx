"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

function AttendeeNav() {
  const pathname = usePathname();

  const links = [
    { href: "/", label: "Home" },
    { href: "/tools", label: "Tools" },
    { href: "/results", label: "Results" },
  ];

  return (
    <nav className="flex items-center gap-6 px-4 py-3 border-b border-gray-200 bg-white">
      <span className="text-base font-semibold">Ethics Toolkit</span>
      <div className="flex items-center gap-4">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`min-h-[2.75rem] min-w-[2.75rem] flex items-center justify-center px-3 text-base ${
              pathname === link.href
                ? "text-black font-medium"
                : "text-gray-500"
            }`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

function FacilitatorNav() {
  const pathname = usePathname();

  const links = [
    { href: "/facilitator", label: "Home" },
    { href: "/facilitator/dashboard", label: "Dashboard" },
  ];

  return (
    <nav className="flex items-center gap-6 px-4 py-3 border-b border-gray-200 bg-gray-50">
      <span className="text-base font-semibold">Facilitator</span>
      <div className="flex items-center gap-4">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`min-h-[2.75rem] min-w-[2.75rem] flex items-center justify-center px-3 text-base ${
              pathname === link.href
                ? "text-black font-medium"
                : "text-gray-500"
            }`}
          >
            {link.label}
          </Link>
        ))}
      </div>
    </nav>
  );
}

export { AttendeeNav, FacilitatorNav };
