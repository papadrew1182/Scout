/**
 * Login screen — email + password for Scout private launch.
 */

import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useAuth } from "../lib/auth";
import { colors } from "../lib/styles";

export function LoginScreen() {
  const { login, error, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const handleLogin = async () => {
    if (!email.trim() || !password.trim() || busy) return;
    setBusy(true);
    setLocalError(null);
    try {
      await login(email.trim(), password.trim());
    } catch {
      setLocalError("Invalid email or password");
    } finally {
      setBusy(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.container}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <Text style={styles.brand}>Scout</Text>
        <Text style={styles.subtitle}>Family Operations</Text>

        {(localError || error) && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{localError || error}</Text>
          </View>
        )}

        <TextInput
          style={styles.input}
          value={email}
          onChangeText={setEmail}
          placeholder="Email"
          placeholderTextColor={colors.textPlaceholder}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
        />

        <TextInput
          style={styles.input}
          value={password}
          onChangeText={setPassword}
          placeholder="Password"
          placeholderTextColor={colors.textPlaceholder}
          secureTextEntry
          onSubmitEditing={handleLogin}
        />

        <Pressable
          style={[styles.button, busy && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={busy || !email.trim() || !password.trim()}
        >
          <Text style={styles.buttonText}>
            {busy ? "Signing in..." : "Sign In"}
          </Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    padding: 32,
    width: "100%",
    maxWidth: 400,
    alignItems: "center",
  },
  brand: {
    color: colors.accent,
    fontSize: 32,
    fontWeight: "800",
    letterSpacing: 2,
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    marginTop: 4,
    marginBottom: 28,
  },
  input: {
    width: "100%",
    backgroundColor: colors.surfaceMuted,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: 16,
    paddingVertical: 14,
    color: colors.textPrimary,
    fontSize: 15,
    marginBottom: 12,
  },
  button: {
    width: "100%",
    backgroundColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: {
    backgroundColor: colors.buttonDisabledBg,
  },
  buttonText: {
    color: colors.buttonPrimaryText,
    fontSize: 16,
    fontWeight: "700",
  },
  errorBox: {
    backgroundColor: colors.msgError,
    borderRadius: 8,
    padding: 12,
    width: "100%",
    marginBottom: 12,
  },
  errorText: {
    color: colors.msgErrorText,
    fontSize: 13,
    textAlign: "center",
  },
});
