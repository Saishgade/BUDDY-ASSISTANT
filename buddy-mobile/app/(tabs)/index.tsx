import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ScrollView,
  Linking,
} from "react-native";

interface CommandPayload {
  action?: string;
  target?: string;
  value?: string;
  metadata?: Record<string, any>;
}

export default function HomeScreen() {
  const [host, setHost] = useState("");
  const [status, setStatus] = useState("🔴 Not Connected");
  const [pairCode, setPairCode] = useState("");
  const [pairCodeFromPC, setPairCodeFromPC] = useState("");
  const [isPaired, setIsPaired] = useState(false);
  const [loading, setLoading] = useState(false);
  const [commandLog, setCommandLog] = useState<string[]>([]);

  const getHost = () => host.trim();

  const appendLog = (message: string) => {
    setCommandLog((current) => [message, ...current].slice(0, 10));
  };

  const buildUrl = (path: string) => {
    const targetHost = getHost();
    if (!targetHost) {
      throw new Error("Missing PC IP");
    }
    return `http://${targetHost}:8765${path}`;
  };

  const fetchJson = async (path: string) => {
    const response = await fetch(buildUrl(path));
    const text = await response.text();
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`Invalid JSON response: ${text}`);
    }
  };

  const connectToPC = async () => {
    try {
      setLoading(true);
      setStatus("🟡 Connecting...");
      const data = await fetchJson("/connect");
      if (data.ok) {
        setStatus("🟢 Connected");
        Alert.alert("Buddy", "Connected successfully!");
      } else {
        setStatus("🔴 Connection failed");
        Alert.alert("Buddy", data.message || "Connection failed");
      }
    } catch (err: any) {
      setStatus("🔴 Connection failed");
      Alert.alert("Buddy", err.message || "Unable to connect to PC.");
    } finally {
      setLoading(false);
    }
  };

  const refreshPairInfo = async () => {
    try {
      setLoading(true);
      setStatus("🟡 Fetching pairing info...");
      const data = await fetchJson("/pair-info");
      if (data.ok) {
        setPairCodeFromPC(data.pair_code || "");
        setStatus("🟢 Pairing info loaded.");
      } else {
        setStatus("🔴 Failed to load pairing info");
        Alert.alert("Buddy", data.message || "Unable to fetch pairing information.");
      }
    } catch (err: any) {
      setStatus("🔴 Failed to load pairing info");
      Alert.alert("Buddy", err.message || "Cannot reach PC to fetch pairing info.");
    } finally {
      setLoading(false);
    }
  };

  const pairWithPC = async () => {
    try {
      setLoading(true);
      setStatus("🟡 Pairing...");
      const codeToUse = pairCode.trim() || pairCodeFromPC.trim();
      if (!codeToUse) {
        Alert.alert("Buddy", "Please enter a pairing code or refresh pairing info.");
        return;
      }
      const data = await fetchJson(`/pair?code=${encodeURIComponent(codeToUse)}`);
      if (data.ok) {
        setStatus("🟢 Paired");
        setIsPaired(true);
        appendLog(`Paired with PC using code ${codeToUse}`);
        Alert.alert("Buddy", "Pairing successful!");
      } else {
        setStatus("🔴 Pairing failed");
        setIsPaired(false);
        Alert.alert("Buddy", data.message || "Pairing failed");
      }
    } catch (err: any) {
      setStatus("🔴 Pairing failed");
      setIsPaired(false);
      Alert.alert("Buddy", err.message || "Unable to pair with the PC right now.");
    } finally {
      setLoading(false);
    }
  };

  const resolveOpenAppUrl = (target: string) => {
    const normalizedTarget = (target || "").trim().toLowerCase();
    if (!normalizedTarget) {
      return "";
    }

    if (
      normalizedTarget.startsWith("android-app://") ||
      normalizedTarget.startsWith("intent://") ||
      normalizedTarget.startsWith("http://") ||
      normalizedTarget.startsWith("https://") ||
      normalizedTarget.startsWith("whatsapp://") ||
      normalizedTarget.startsWith("tg://") ||
      normalizedTarget.startsWith("spotify://") ||
      normalizedTarget.startsWith("youtube://") ||
      normalizedTarget.startsWith("geo:") ||
      normalizedTarget.startsWith("googlechrome://")
    ) {
      return normalizedTarget;
    }

    const packageMap: Record<string, string> = {
      whatsapp: "com.whatsapp",
      telegram: "org.telegram.messenger",
      youtube: "com.google.android.youtube",
      "youtube music": "com.google.android.apps.youtube.music",
      spotify: "com.spotify.music",
      "google keep": "com.google.android.keep",
      keep: "com.google.android.keep",
      contacts: "com.android.contacts",
      chrome: "com.android.chrome",
      maps: "com.google.android.apps.maps",
      "google maps": "com.google.android.apps.maps",
      gmail: "com.google.android.gm",
      phone: "com.android.dialer",
      settings: "com.android.settings",
      camera: "com.android.camera",
      calculator: "com.android.calculator2",
    };

    if (packageMap[normalizedTarget]) {
      return `intent://#Intent;package=${packageMap[normalizedTarget]};S.browser_fallback_url=https://play.google.com/store/apps/details?id=${packageMap[normalizedTarget]};end`;
    }

    return `intent://#Intent;package=${normalizedTarget};S.browser_fallback_url=https://play.google.com/store/apps/details?id=${normalizedTarget};end`;
  };

  const buildCommandUrl = (command: CommandPayload) => {
    const action = (command.action || "").toLowerCase();
    const target = command.target || "";
    const value = command.value || "";
    const metadata = command.metadata || {};

    if (action === "call") {
      return `tel:${target}`;
    }

    if (action === "sms") {
      return `sms:${target}?body=${encodeURIComponent(value)}`;
    }

    if (action === "open_app") {
      return resolveOpenAppUrl(target);
    }

    if (action === "play_media") {
      const query = encodeURIComponent(value || target || "");
      if (target.toLowerCase().includes("spotify")) {
        return `https://open.spotify.com/search/${query}`;
      }
      return `https://www.youtube.com/results?search_query=${query}`;
    }

    if (action === "make_note") {
      return "https://keep.google.com";
    }

    if (action === "send_message") {
      const platform = (metadata.platform || "").toLowerCase();
      if (platform === "whatsapp") {
        return `whatsapp://send?text=${encodeURIComponent(value || target)}`;
      }
      return `sms:${target}?body=${encodeURIComponent(value)}`;
    }

    return "";
  };

  const executeMobileCommand = async (command: CommandPayload) => {
    const url = buildCommandUrl(command);
    if (!url) {
      appendLog(`Unsupported command: ${command.action}`);
      Alert.alert("Buddy", `Unsupported command: ${command.action}`);
      return;
    }

    try {
      const canOpen = await Linking.canOpenURL(url);
      if (canOpen) {
        await Linking.openURL(url);
        appendLog(`Executed ${command.action}: ${url}`);
      } else {
        appendLog(`Cannot open URL: ${url}`);
        Alert.alert("Buddy", `Cannot open URL for command: ${command.action}`);
      }
    } catch (err: any) {
      appendLog(`Command error: ${err.message}`);
      Alert.alert("Buddy", `Command error: ${err.message}`);
    }
  };

  const fetchNextCommand = async () => {
    if (!isPaired) {
      return;
    }

    try {
      const data = await fetchJson("/commands/next");
      if (data.ok && data.command) {
        appendLog(`Received command: ${data.command.action}`);
        await executeMobileCommand(data.command as CommandPayload);
      }
    } catch (err: any) {
      appendLog(`Command poll failed: ${err.message}`);
    }
  };

  useEffect(() => {
    if (!isPaired) {
      return;
    }

    const interval = setInterval(fetchNextCommand, 5000);
    return () => clearInterval(interval);
  }, [isPaired, host]);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.logo}>🤖</Text>
      <Text style={styles.title}>Buddy Mobile</Text>
      <Text style={styles.subtitle}>Control Buddy from your phone</Text>

      <View style={styles.statusBox}>
        <Text style={styles.statusLabel}>Status</Text>
        <Text style={styles.statusDisconnected}>{status}</Text>
      </View>

      <TextInput
        style={styles.input}
        placeholder="PC local IP address"
        placeholderTextColor="#94A3B8"
        value={host}
        onChangeText={setHost}
        autoCapitalize="none"
        keyboardType="default"
      />

      <TextInput
        style={styles.input}
        placeholder="Enter pairing code"
        placeholderTextColor="#94A3B8"
        value={pairCode}
        onChangeText={setPairCode}
        keyboardType="number-pad"
      />

      <Text style={styles.hint}>Latest code from PC: {pairCodeFromPC || "none loaded"}</Text>

      <TouchableOpacity style={styles.button} onPress={connectToPC} disabled={loading}>
        <Text style={styles.buttonText}>{loading ? "Working..." : "Connect to PC"}</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.secondaryButton} onPress={refreshPairInfo} disabled={loading}>
        <Text style={styles.secondaryButtonText}>Refresh Pairing Info</Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.secondaryButton} onPress={pairWithPC} disabled={loading}>
        <Text style={styles.secondaryButtonText}>Pair with PC</Text>
      </TouchableOpacity>

      <View style={styles.actionsBox}>
        <Text style={styles.actionsTitle}>Manual commands</Text>
        <View style={styles.row}>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "open_app", target: "whatsapp" })}>
            <Text style={styles.actionButtonText}>WhatsApp</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "open_app", target: "telegram" })}>
            <Text style={styles.actionButtonText}>Telegram</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.row}>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "call", target: "1234567890" })}>
            <Text style={styles.actionButtonText}>Call</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "sms", target: "1234567890", value: "Hello from Buddy" })}>
            <Text style={styles.actionButtonText}>SMS</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.row}>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "play_media", target: "youtube", value: "shape of you" })}>
            <Text style={styles.actionButtonText}>YouTube</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "play_media", target: "spotify", value: "Lo-fi beats" })}>
            <Text style={styles.actionButtonText}>Spotify</Text>
          </TouchableOpacity>
        </View>
        <View style={styles.row}>
          <TouchableOpacity style={styles.actionButton} onPress={() => executeMobileCommand({ action: "make_note", value: "Note from Buddy" })}>
            <Text style={styles.actionButtonText}>Google Keep</Text>
          </TouchableOpacity>
        </View>
      </View>

      <View style={styles.logBox}>
        <Text style={styles.actionsTitle}>Command log</Text>
        {commandLog.map((entry, index) => (
          <Text key={index} style={styles.logText}>{entry}</Text>
        ))}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: "#101827",
    justifyContent: "center",
    alignItems: "center",
    padding: 25,
  },
  logo: {
    fontSize: 70,
    marginBottom: 15,
  },
  title: {
    fontSize: 32,
    fontWeight: "bold",
    color: "#FFFFFF",
  },
  subtitle: {
    marginTop: 10,
    fontSize: 16,
    color: "#B0B0B0",
    textAlign: "center",
    marginBottom: 25,
  },
  statusBox: {
    width: "100%",
    backgroundColor: "#1E293B",
    borderRadius: 12,
    padding: 20,
    marginBottom: 15,
  },
  statusLabel: {
    color: "#94A3B8",
    fontSize: 15,
    marginBottom: 8,
  },
  statusDisconnected: {
    color: "#FFFFFF",
    fontSize: 20,
    fontWeight: "bold",
  },
  input: {
    width: "100%",
    backgroundColor: "#1E293B",
    color: "#FFFFFF",
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: 12,
  },
  hint: {
    width: "100%",
    color: "#A8D8EC",
    marginBottom: 14,
  },
  button: {
    backgroundColor: "#2563EB",
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 10,
    marginBottom: 10,
    width: "100%",
    alignItems: "center",
  },
  secondaryButton: {
    backgroundColor: "#0F766E",
    paddingVertical: 14,
    paddingHorizontal: 40,
    borderRadius: 10,
    marginBottom: 15,
    width: "100%",
    alignItems: "center",
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 18,
    fontWeight: "bold",
  },
  secondaryButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "bold",
  },
  actionsBox: {
    width: "100%",
    backgroundColor: "#111827",
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
  },
  actionsTitle: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "bold",
    marginBottom: 10,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 10,
  },
  actionButton: {
    flex: 1,
    backgroundColor: "#334155",
    borderRadius: 10,
    paddingVertical: 10,
    marginHorizontal: 4,
    alignItems: "center",
  },
  actionButtonText: {
    color: "#FFFFFF",
    fontSize: 14,
    fontWeight: "600",
  },
  logBox: {
    width: "100%",
    backgroundColor: "#0f172a",
    borderRadius: 12,
    padding: 15,
  },
  logText: {
    color: "#A8D8EC",
    fontSize: 13,
    marginBottom: 6,
  },
  footer: {
    color: "#94A3B8",
    fontSize: 14,
    textAlign: "center",
  },
});
