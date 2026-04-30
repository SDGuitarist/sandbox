import Link from "next/link";

const tools = [
  {
    href: "/tools/disclosure",
    title: "AI Disclosure Generator",
    description: "Generate disclosure statements for AI usage in your project.",
  },
  {
    href: "/tools/festival",
    title: "Festival Policy Lookup",
    description: "Search festival AI policies before you submit.",
  },
  {
    href: "/tools/risk",
    title: "Project Risk Scanner",
    description: "Score your project's legal, ethical, and reputational risk.",
  },
  {
    href: "/tools/provenance",
    title: "AI Provenance Chain",
    description: "Document who made what and how AI was involved.",
  },
  {
    href: "/tools/budget",
    title: "Budget vs. Ethics Calculator",
    description: "Compare AI costs against fair human compensation.",
  },
];

export default function AttendeePage() {
  return (
    <div className="px-4 py-6 max-w-lg mx-auto">
      <h1 className="text-2xl font-bold mb-2">Ethics Toolkit</h1>
      <p className="text-base text-gray-600 mb-6">
        Navigate AI use in filmmaking with confidence.
      </p>
      <ul className="space-y-3">
        {tools.map((tool) => (
          <li key={tool.href}>
            <Link
              href={tool.href}
              className="block min-h-[2.75rem] p-4 rounded-lg border border-gray-200 active:bg-gray-50"
            >
              <span className="text-base font-medium block">{tool.title}</span>
              <span className="text-sm text-gray-500 block mt-1">
                {tool.description}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
