import { HealthProfileDashboard } from "@/components/health-profile/HealthProfileDashboard";

export default function ProfilePage() {
  return (
    <div data-testid="profile-scroll-container" className="h-full min-h-0 overflow-y-auto overscroll-contain [scrollbar-gutter:stable]">
      <HealthProfileDashboard />
    </div>
  );
}
