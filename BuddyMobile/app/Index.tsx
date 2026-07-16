import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  Alert,
} from "react-native";

export default function HomeScreen() {

  const [status, setStatus] = useState("🔴 Not Connected");

  async function connectToPC() {
    const PC_IP = "10.31.254.27";

    try {
      setStatus("🟡 Connecting...");

      const response = await fetch(`http://${PC_IP}:8765/connect`);

      const text = await response.text();

      console.log(text);

      Alert.alert("Server Response", text);

      setStatus("🟢 Connected");
    } catch (error: any) {
      console.log(error);

      Alert.alert("Error", JSON.stringify(error));

      setStatus("🔴 Connection Failed");
    }
  }

  return (
  <View style={styles.container}>

    <Text style={styles.title}>🤖 Buddy Mobile</Text>

    <Text style={styles.text}>
      {status}
    </Text>

    <TouchableOpacity
      style={{
        backgroundColor: "#2563EB",
        padding: 15,
        marginTop: 30,
        borderRadius: 10,
      }}
      onPress={connectToPC}
    >
      <Text
        style={{
          color: "white",
          fontSize: 18,
          fontWeight: "bold",
        }}
      >
        Connect to PC
      </Text>
    </TouchableOpacity>

  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#111827",
    justifyContent: "center",
    alignItems: "center",
  },
  title: {
    fontSize: 30,
    fontWeight: "bold",
    color: "#ffffff",
    marginBottom: 20,
  },
  text: {
    fontSize: 18,
    color: "#ffffff",
    marginVertical: 5,
  },
});