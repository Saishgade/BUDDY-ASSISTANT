import React, { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, TextInput, View, TouchableOpacity, SafeAreaView, Alert } from 'react-native';
import { pairWithBuddy, buildPairingUrl, sendBuddyCommand } from './src/pairingService';

export default function App() {
  const [code, setCode] = useState('');
  const [host, setHost] = useState('192.168.1.10');
  const [status, setStatus] = useState('Enter the pairing code from Buddy.');
  const [paired, setPaired] = useState(false);

  const handlePair = async () => {
    if (!code.trim()) {
      Alert.alert('Missing code', 'Please enter the code shown on your PC.');
      return;
    }

    setStatus('Pairing with Buddy...');
    try {
      const result = await pairWithBuddy(code.trim(), host.trim());
      setStatus(result.message || 'Pairing complete.');
      setPaired(Boolean(result.ok));
    } catch (error) {
      setStatus(`Pairing failed: ${error.message}`);
      setPaired(false);
    }
  };

  const handleQuickAction = async (action) => {
    if (!paired) {
      Alert.alert('Not paired', 'Pair with your PC first.');
      return;
    }

    const normalizedAction = action.toLowerCase().replace(/\s+/g, '_');
    setStatus(`Sending ${normalizedAction}...`);
    try {
      const payload = {
        open_app: { target: 'whatsapp' },
        make_note: { value: 'New note from Buddy Mobile' },
        play_media: { target: 'youtube', value: 'shape of you' },
      }[normalizedAction] || {};
      const result = await sendBuddyCommand(normalizedAction, payload, host.trim());
      setStatus(result.message || `${action} sent.`);
    } catch (error) {
      setStatus(`Action failed: ${error.message}`);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="light" />
      <View style={styles.card}>
        <Text style={styles.badge}>Dedicated mobile companion</Text>
        <Text style={styles.title}>Buddy Mobile</Text>
        <Text style={styles.subtitle}>Pair with your PC securely over your local network.</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter pairing code"
          placeholderTextColor="#7f9aac"
          value={code}
          onChangeText={setCode}
          keyboardType="number-pad"
          autoCapitalize="none"
        />
        <TextInput
          style={styles.input}
          placeholder="PC host (e.g. 192.168.1.10)"
          placeholderTextColor="#7f9aac"
          value={host}
          onChangeText={setHost}
          autoCapitalize="none"
        />
        <TouchableOpacity style={styles.button} onPress={handlePair}>
          <Text style={styles.buttonText}>Pair with PC</Text>
        </TouchableOpacity>
        <Text style={styles.statusText}>{status}</Text>
        <Text style={styles.hint}>{buildPairingUrl(code || '0000')}</Text>

        {paired ? (
          <View style={styles.actionsContainer}>
            <TouchableOpacity style={styles.actionButton} onPress={() => handleQuickAction('Open app')}>
              <Text style={styles.actionButtonText}>Open App</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionButton} onPress={() => handleQuickAction('Make note')}>
              <Text style={styles.actionButtonText}>Make Note</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.actionButton} onPress={() => handleQuickAction('Play media')}>
              <Text style={styles.actionButtonText}>Play Media</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#07131e',
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    width: '90%',
    maxWidth: 480,
    backgroundColor: '#112235',
    borderRadius: 18,
    padding: 24,
  },
  badge: {
    color: '#9de8ff',
    fontSize: 12,
    marginBottom: 10,
    textTransform: 'uppercase',
    letterSpacing: 1.2,
  },
  title: {
    color: 'white',
    fontSize: 30,
    fontWeight: '700',
    marginBottom: 8,
  },
  subtitle: {
    color: '#aac1cd',
    fontSize: 15,
    marginBottom: 20,
    lineHeight: 22,
  },
  button: {
    backgroundColor: '#2fa4d8',
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
  },
  buttonText: {
    color: 'white',
    fontWeight: '700',
    fontSize: 16,
  },
  input: {
    backgroundColor: '#0d1a26',
    borderColor: '#2d5570',
    borderWidth: 1,
    borderRadius: 10,
    color: 'white',
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 14,
  },
  statusText: {
    color: '#a8d8ec',
    marginTop: 12,
    fontSize: 14,
  },
  hint: {
    color: '#5f8293',
    marginTop: 10,
    fontSize: 12,
  },
  actionsContainer: {
    marginTop: 16,
    gap: 8,
  },
  actionButton: {
    backgroundColor: '#1c4f6b',
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  actionButtonText: {
    color: 'white',
    fontWeight: '600',
    textAlign: 'center',
  },
});
