import { useState } from "react";
import { useLocalSearchParams } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  addProjectBudgetEntry,
  addProjectMilestone,
  addProjectTask,
  updateProjectTask,
  useProject,
  useProjectHealth,
} from "../../lib/projects";
import { colors, fonts, shared } from "../../lib/styles";

type Tab = "tasks" | "milestones" | "budget" | "info";

const TAB_LABEL: Record<Tab, string> = {
  tasks: "Tasks",
  milestones: "Milestones",
  budget: "Budget",
  info: "Info",
};

export default function ProjectDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("tasks");
  const { detail, loading, reload, error } = useProject(id ?? null);
  const { health } = useProjectHealth(id ?? null);

  if (loading && !detail) return <ActivityIndicator color={colors.purple} style={{ margin: 24 }} />;
  if (error) return <Text style={styles.errorText}>{error}</Text>;
  if (!detail) return null;

  const { project, tasks, milestones, budget_entries } = detail;

  return (
    <ScrollView style={shared.pageContainer} contentContainerStyle={styles.content}>
      <Text style={styles.h1}>{project.name}</Text>
      <Text style={styles.subtitle}>
        {project.category} · {project.status} · starts {project.start_date}
      </Text>
      {health && (
        <Text style={styles.subtitle}>
          {health.tasks_done}/{health.tasks_total} tasks complete ({health.completion_percent}%){" "}
          · {health.tasks_overdue} overdue
        </Text>
      )}

      <View style={styles.tabsRow}>
        {(Object.keys(TAB_LABEL) as Tab[]).map((t) => (
          <Pressable
            key={t}
            style={[styles.tab, tab === t && styles.tabActive]}
            onPress={() => setTab(t)}
            accessibilityRole="button"
            accessibilityLabel={`${TAB_LABEL[t]} tab`}
          >
            <Text style={[styles.tabText, tab === t && styles.tabTextActive]}>
              {TAB_LABEL[t]}
            </Text>
          </Pressable>
        ))}
      </View>

      {tab === "tasks" && (
        <TasksTab
          projectId={project.id}
          tasks={tasks}
          onChange={reload}
        />
      )}
      {tab === "milestones" && (
        <MilestonesTab
          projectId={project.id}
          milestones={milestones}
          onChange={reload}
        />
      )}
      {tab === "budget" && (
        <BudgetTab
          projectId={project.id}
          entries={budget_entries}
          budgetCents={project.budget_cents}
          onChange={reload}
        />
      )}
      {tab === "info" && (
        <View style={shared.card}>
          <Text style={shared.cardTitle}>Info</Text>
          <Text style={styles.muted}>Category: {project.category}</Text>
          <Text style={styles.muted}>Status: {project.status}</Text>
          <Text style={styles.muted}>Start: {project.start_date}</Text>
          {project.target_end_date && (
            <Text style={styles.muted}>Target end: {project.target_end_date}</Text>
          )}
          {project.budget_cents != null && (
            <Text style={styles.muted}>
              Budget: ${(project.budget_cents / 100).toFixed(2)}
            </Text>
          )}
          {project.description && <Text style={styles.body}>{project.description}</Text>}
        </View>
      )}
    </ScrollView>
  );
}

function TasksTab({
  projectId,
  tasks,
  onChange,
}: {
  projectId: string;
  tasks: { id: string; title: string; status: string; due_date: string | null }[];
  onChange: () => void;
}) {
  const [title, setTitle] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [adding, setAdding] = useState(false);

  return (
    <View style={{ gap: 8 }}>
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Add task</Text>
        <TextInput
          style={styles.input}
          value={title}
          onChangeText={setTitle}
          placeholder="Task title"
          placeholderTextColor={colors.muted}
        />
        <TextInput
          style={styles.input}
          value={dueDate}
          onChangeText={setDueDate}
          placeholder="Due date (YYYY-MM-DD, optional)"
          placeholderTextColor={colors.muted}
        />
        <Pressable
          style={styles.btnPrimary}
          disabled={adding || !title}
          onPress={async () => {
            setAdding(true);
            try {
              await addProjectTask(projectId, { title, due_date: dueDate || null });
              setTitle("");
              setDueDate("");
              onChange();
            } finally {
              setAdding(false);
            }
          }}
          accessibilityRole="button"
          accessibilityLabel="Add task"
        >
          <Text style={styles.btnPrimaryText}>{adding ? "Adding…" : "Add task"}</Text>
        </Pressable>
      </View>

      {tasks.length === 0 ? (
        <Text style={styles.muted}>No tasks yet.</Text>
      ) : (
        tasks.map((t) => (
          <View key={t.id} style={shared.card}>
            <Text style={styles.taskTitle}>{t.title}</Text>
            <Text style={styles.muted}>
              {t.status} {t.due_date ? `· due ${t.due_date}` : ""}
            </Text>
            {t.status !== "done" && (
              <Pressable
                style={styles.btnSecondary}
                onPress={async () => {
                  await updateProjectTask(projectId, t.id, { status: "done" });
                  onChange();
                }}
                accessibilityRole="button"
                accessibilityLabel={`Mark ${t.title} complete`}
              >
                <Text style={styles.btnSecondaryText}>Mark complete</Text>
              </Pressable>
            )}
          </View>
        ))
      )}
    </View>
  );
}

function MilestonesTab({
  projectId,
  milestones,
  onChange,
}: {
  projectId: string;
  milestones: { id: string; name: string; target_date: string; is_complete: boolean }[];
  onChange: () => void;
}) {
  const [name, setName] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [adding, setAdding] = useState(false);

  return (
    <View style={{ gap: 8 }}>
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Add milestone</Text>
        <TextInput
          style={styles.input}
          value={name}
          onChangeText={setName}
          placeholder="Milestone name"
          placeholderTextColor={colors.muted}
        />
        <TextInput
          style={styles.input}
          value={targetDate}
          onChangeText={setTargetDate}
          placeholder="Target date (YYYY-MM-DD)"
          placeholderTextColor={colors.muted}
        />
        <Pressable
          style={styles.btnPrimary}
          disabled={adding || !name || !targetDate}
          onPress={async () => {
            setAdding(true);
            try {
              await addProjectMilestone(projectId, { name, target_date: targetDate });
              setName("");
              setTargetDate("");
              onChange();
            } finally {
              setAdding(false);
            }
          }}
          accessibilityRole="button"
          accessibilityLabel="Add milestone"
        >
          <Text style={styles.btnPrimaryText}>{adding ? "Adding…" : "Add milestone"}</Text>
        </Pressable>
      </View>
      {milestones.map((m) => (
        <View key={m.id} style={shared.card}>
          <Text style={styles.taskTitle}>{m.name}</Text>
          <Text style={styles.muted}>
            target {m.target_date} {m.is_complete ? "· complete" : ""}
          </Text>
        </View>
      ))}
    </View>
  );
}

function BudgetTab({
  projectId,
  entries,
  budgetCents,
  onChange,
}: {
  projectId: string;
  entries: { id: string; amount_cents: number; kind: string; vendor: string | null; notes: string | null; recorded_at: string }[];
  budgetCents: number | null;
  onChange: () => void;
}) {
  const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"estimate" | "expense" | "refund">("expense");
  const [vendor, setVendor] = useState("");
  const [adding, setAdding] = useState(false);

  const spent = entries
    .filter((e) => e.kind === "expense")
    .reduce((sum, e) => sum + e.amount_cents, 0);

  return (
    <View style={{ gap: 8 }}>
      <View style={shared.card}>
        <Text style={shared.cardTitle}>
          Spent ${(spent / 100).toFixed(2)}
          {budgetCents != null ? ` of $${(budgetCents / 100).toFixed(2)}` : ""}
        </Text>
      </View>
      <View style={shared.card}>
        <Text style={shared.cardTitle}>Add entry</Text>
        <TextInput
          style={styles.input}
          value={amount}
          onChangeText={setAmount}
          keyboardType="numeric"
          placeholder="Amount (cents)"
          placeholderTextColor={colors.muted}
        />
        <View style={styles.kindRow}>
          {(["estimate", "expense", "refund"] as const).map((k) => (
            <Pressable
              key={k}
              onPress={() => setKind(k)}
              style={[styles.kindChip, kind === k && styles.kindChipActive]}
              accessibilityRole="button"
              accessibilityLabel={`Kind ${k}`}
            >
              <Text
                style={[styles.kindChipText, kind === k && styles.kindChipTextActive]}
              >
                {k}
              </Text>
            </Pressable>
          ))}
        </View>
        <TextInput
          style={styles.input}
          value={vendor}
          onChangeText={setVendor}
          placeholder="Vendor (optional)"
          placeholderTextColor={colors.muted}
        />
        <Pressable
          style={styles.btnPrimary}
          disabled={adding || !amount}
          onPress={async () => {
            setAdding(true);
            try {
              await addProjectBudgetEntry(projectId, {
                amount_cents: parseInt(amount, 10),
                kind,
                vendor: vendor || undefined,
              });
              setAmount("");
              setVendor("");
              onChange();
            } finally {
              setAdding(false);
            }
          }}
          accessibilityRole="button"
          accessibilityLabel="Add budget entry"
        >
          <Text style={styles.btnPrimaryText}>{adding ? "Saving…" : "Save entry"}</Text>
        </Pressable>
      </View>
      {entries.map((e) => (
        <View key={e.id} style={shared.card}>
          <Text style={styles.taskTitle}>
            ${(e.amount_cents / 100).toFixed(2)} · {e.kind}
            {e.vendor ? ` · ${e.vendor}` : ""}
          </Text>
          <Text style={styles.muted}>{new Date(e.recorded_at).toLocaleDateString()}</Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  content: { padding: 20, gap: 12, paddingBottom: 48 },
  h1: { fontSize: 22, fontWeight: "600", color: colors.text, fontFamily: fonts.body },
  subtitle: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  body: { fontSize: 13, color: colors.text, fontFamily: fonts.body, marginTop: 8 },
  muted: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  errorText: { fontSize: 12, color: colors.red, fontFamily: fonts.body, margin: 20 },
  taskTitle: { fontSize: 13, color: colors.text, fontWeight: "500", fontFamily: fonts.body },

  tabsRow: { flexDirection: "row", gap: 6 },
  tab: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 8,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
  },
  tabActive: { borderBottomColor: colors.purple },
  tabText: { fontSize: 12, color: colors.muted, fontFamily: fonts.body },
  tabTextActive: { color: colors.purple, fontWeight: "600" },

  input: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 9,
    fontSize: 12,
    color: colors.text,
    marginBottom: 8,
    fontFamily: fonts.body,
  },
  btnPrimary: {
    backgroundColor: colors.purple,
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: "center",
  },
  btnPrimaryText: { color: "#FFFFFF", fontSize: 12, fontWeight: "500", fontFamily: fonts.body },
  btnSecondary: {
    marginTop: 8,
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
    alignSelf: "flex-start",
  },
  btnSecondaryText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },

  kindRow: { flexDirection: "row", gap: 6, marginBottom: 8 },
  kindChip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  kindChipActive: { backgroundColor: colors.purple, borderColor: colors.purple },
  kindChipText: { color: colors.text, fontSize: 12, fontFamily: fonts.body },
  kindChipTextActive: { color: "#FFFFFF" },
});
