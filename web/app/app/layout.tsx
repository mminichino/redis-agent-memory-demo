import { ChatHealthProvider } from "@/components/chat/chat-health-context";

export default function AppSectionLayout({ children }: { children: React.ReactNode }) {
  return <ChatHealthProvider>{children}</ChatHealthProvider>;
}
