"use client";

interface MobileActionBarProps {
  children: React.ReactNode;
}

export function MobileActionBar({ children }: MobileActionBarProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-3 safe-area-bottom z-50">
      <div className="flex items-center justify-center gap-3">
        {children}
      </div>
    </div>
  );
}

interface ActionButtonProps {
  onClick?: () => void;
  href?: string;
  label: string;
  variant?: "primary" | "secondary";
  type?: "button" | "submit";
  disabled?: boolean;
}

export function ActionButton({
  onClick,
  href,
  label,
  variant = "primary",
  type = "button",
  disabled = false,
}: ActionButtonProps) {
  const baseStyles =
    "min-h-[2.75rem] min-w-[2.75rem] px-6 py-3 text-base font-medium rounded-lg w-full text-center";
  const variantStyles =
    variant === "primary"
      ? "bg-black text-white"
      : "bg-white text-black border border-gray-300";
  const disabledStyles = disabled ? "opacity-50 cursor-not-allowed" : "";

  if (href) {
    return (
      <a
        href={href}
        className={`${baseStyles} ${variantStyles} ${disabledStyles} block`}
      >
        {label}
      </a>
    );
  }

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`${baseStyles} ${variantStyles} ${disabledStyles}`}
    >
      {label}
    </button>
  );
}
