import InternalDashboard from "@/components/InternalDashboard";
import Chrome from "@/components/Chrome";
import { VENDOR_NAME } from "@/lib/branding";

// Internal destination: cohort god-view (brutalist system). No app-level gate; access is the deployment's boundary.
export default function InternalPage() {
  return (
    <Chrome
      active="Internal"
      restricted
      breadcrumb="Hub / Internal / Cohort Intelligence"
      context="Internal Only"
      footerLeft={VENDOR_NAME}
      footerRight="Internal Only — Do Not Distribute"
    >
      <InternalDashboard />
    </Chrome>
  );
}
