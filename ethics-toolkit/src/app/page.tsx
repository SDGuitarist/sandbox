import Link from "next/link";
import { APP_NAME } from "@/lib/constants";

const tools = [
  { name: "AI Disclosure Generator", href: "/tools/disclosure" },
  { name: "Festival Policy Lookup", href: "/tools/festival" },
  { name: "Project Risk Scanner", href: "/tools/risk" },
  { name: "Provenance Chain Builder", href: "/tools/provenance" },
  { name: "Budget vs. Ethics Calculator", href: "/tools/budget" },
];

export default function HomePage() {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12">
      <h1 className="text-3xl font-bold mb-8">{APP_NAME}</h1>
      <nav>
        <ul className="space-y-4">
          {tools.map((tool) => (
            <li key={tool.href}>
              <Link
                href={tool.href}
                className="block w-full min-h-[44px] px-6 py-3 text-center rounded-lg bg-gray-900 text-white hover:bg-gray-700"
              >
                {tool.name}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
