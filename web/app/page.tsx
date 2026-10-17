import ChatApp from "@/components/ChatApp";
import Chrome from "@/components/Chrome";

export default function Home() {
  return (
    <Chrome active="Chat" breadcrumb="Hub / Chat / Discovery" context="Discovery" maxWidth={1100}>
      <ChatApp />
    </Chrome>
  );
}
