import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { Slot, usePathname } from "expo-router";
import { useFonts, DMSans_400Regular, DMSans_500Medium, DMSans_600SemiBold } from "@expo-google-fonts/dm-sans";
import { DMMono_400Regular, DMMono_500Medium } from "@expo-google-fonts/dm-mono";

import { AuthProvider, useAuth } from "../lib/auth";
import { setApiToken, setApiFamilyId, uploadAttachment } from "../lib/api";
import { installGlobalHandlers } from "../lib/errorReporter";
import { ErrorBoundary } from "../components/ErrorBoundary";

// One-shot install at module load — covers every route in the app
// and every tab. The handler dedupes and no-ops in non-browser envs.
installGlobalHandlers();
import { LoginScreen } from "../components/LoginScreen";
import { NavBar } from "../components/NavBar";
import { ScoutBar } from "../components/ScoutBar";
import { ScoutSidebar } from "../components/ScoutSidebar";
import { ScoutSheet } from "../components/ScoutSheet";
import { BottomTabBar } from "../components/BottomTabBar";
import { useIsDesktop } from "../lib/breakpoint";
import { colors } from "../lib/styles";

function pathToSurface(pathname: string): string {
  if (pathname === "/" ) return "dashboard";
  if (pathname.startsWith("/personal")) return "personal";
  if (pathname.startsWith("/parent"))   return "parent";
  if (pathname.startsWith("/meals"))    return "meals";
  if (pathname.startsWith("/grocery"))  return "grocery";
  if (pathname.startsWith("/child"))    return "child";
  if (pathname.startsWith("/settings")) return "settings";
  return "dashboard";
}

const CHIPS_BY_SURFACE: Record<string, { placeholder: string; chips: string[] }> = {
  dashboard: { placeholder: "Ask Scout anything about your family...", chips: ["What's for dinner?", "Who hasn't done chores?", "Costco list this week", "Plan batch cook", "Remind Tyler"] },
  personal:  { placeholder: "What's on my plate today?",                chips: ["My tasks today", "Upcoming bills", "Add a note", "What's on my calendar?"] },
  parent:    { placeholder: "Summarize what needs my attention today...",chips: ["Morning brief", "Approve purchases", "Kids homework status", "Assign new chores"] },
  meals:     { placeholder: "Generate next week's meal plan...",         chips: ["Generate next week's plan", "What can I make tonight?", "Build grocery list from plan", "Sally's dietary needs"] },
  grocery:   { placeholder: "Add something to the grocery list...",      chips: ["Add item to list", "What do we need from Costco?", "Clear checked items", "Scan receipt"] },
  child:     { placeholder: "Ask Scout anything...",                     chips: ["Help me with homework", "What are my chores?", "How many points do I have?", "Tell me something fun"] },
  settings:  { placeholder: "Ask Scout about settings or family management...", chips: ["Add family member", "Manage chore schedule", "Scout AI settings"] },
};

const SCOUT_PATHS = ["/today", "/rewards", "/calendar", "/control-plane", "/assist"];
function isScoutShell(pathname: string): boolean {
  return SCOUT_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function AppShell() {
  const { token, member, loading } = useAuth();
  const [scoutSheetOpen, setScoutSheetOpen] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const pathname = usePathname();
  const isDesktop = useIsDesktop();

  useEffect(() => {
    setApiToken(token);
    setApiFamilyId(member?.family_id ?? null);
  }, [token, member]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color={colors.purple} />
      </View>
    );
  }

  if (!token || !member) return <LoginScreen />;

  // Session 3 (scout) group keeps its own shell.
  if (isScoutShell(pathname)) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg }}>
        <Slot />
      </View>
    );
  }

  const surface = pathToSurface(pathname);
  const { placeholder, chips } = CHIPS_BY_SURFACE[surface] ?? CHIPS_BY_SURFACE.dashboard;

  // Shell-level ScoutBar submit: upload attachment if present, then open
  // ScoutSheet with the text as initialPrompt. The ScoutSheet will handle
  // the attachment_path if we pass it through pendingPrompt-style, but for
  // simplicity we funnel the text and let ScoutSheet manage the attachment
  // state independently. Chip presses have no attachment.
  const handleScoutSubmit = async (text: string, attachment?: { blob: Blob; name: string }) => {
    if (attachment) {
      try {
        const result = await uploadAttachment(attachment.blob, attachment.name);
        // Open the sheet; the uploaded path isn't plumbed through initialPrompt
        // in this pass — the ScoutSheet will open empty and the user can chat.
        // The attachment was already uploaded; follow-up: thread attachmentPath
        // through ScoutSheet's initialPrompt mechanism.
        setPendingPrompt(text || null);
        setScoutSheetOpen(true);
        return;
      } catch {
        // Fall through: open sheet with text only
      }
    }
    setPendingPrompt(text || null);
    setScoutSheetOpen(true);
  };

  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <NavBar
        onScoutPress={() => setScoutSheetOpen(true)}
        pillLabel={surface === "child" ? "Hey Townes!" : "Scout AI"}
      />
      <ScoutBar
        placeholder={placeholder}
        chips={chips}
        onSubmit={handleScoutSubmit}
        onChipPress={handleScoutSubmit}
      />
      <View style={{ flex: 1, flexDirection: "row" }}>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Slot />
        </View>
        {isDesktop && <ScoutSidebar surface={surface as any} />}
      </View>
      {!isDesktop && <BottomTabBar onScoutPress={() => setScoutSheetOpen(true)} />}
      <ScoutSheet visible={scoutSheetOpen} onClose={() => { setScoutSheetOpen(false); setPendingPrompt(null); }} surface={surface as any} initialPrompt={pendingPrompt} />
    </View>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    DMSans_400Regular,
    DMSans_500Medium,
    DMSans_600SemiBold,
    DMMono_400Regular,
    DMMono_500Medium,
  });

  if (!fontsLoaded) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center", alignItems: "center" }}>
        <ActivityIndicator size="large" color={colors.purple} />
      </View>
    );
  }

  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppShell />
      </AuthProvider>
    </ErrorBoundary>
  );
}
