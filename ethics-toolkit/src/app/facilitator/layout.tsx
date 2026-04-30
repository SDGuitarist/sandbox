import { FacilitatorNav } from "@/components/ui/nav";

export default function FacilitatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <FacilitatorNav />
      <main className="flex-1">{children}</main>
    </div>
  );
}
