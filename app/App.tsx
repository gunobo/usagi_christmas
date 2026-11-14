// SPDX-License-Identifier: MIT
// Copyright (c) 2026 임제민 (gunobo)
import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, FlatList, KeyboardAvoidingView, Modal, Platform, Pressable,
  SafeAreaView, StyleSheet, Text, TextInput, View, useWindowDimensions,
} from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';

// 웹은 같은 도메인(/api), 앱은 배포 주소를 사용
const API = process.env.EXPO_PUBLIC_API_URL ?? (Platform.OS === 'web' ? '' : 'https://usagi.imjemin.co.kr');
const PLAYER_URL = `${API}/player/`;
const C = { bg: '#07090c', card: '#11161c', line: '#283038', text: '#dde3e8', sub: '#8a96a0', accent: '#5fd3a0' };

type Entry = { id: number; name: string; text: string; created_at: string };

function Player() {
  if (Platform.OS === 'web') {
    return <iframe src={PLAYER_URL} style={{ border: 0, width: '100%', height: '100%' }} allow="autoplay" />;
  }
  return (
    <WebView
      source={{ uri: PLAYER_URL }}
      style={{ flex: 1, backgroundColor: C.bg }}
      mediaPlaybackRequiresUserAction={false}
      allowsInlineMediaPlayback
    />
  );
}

function Guestbook({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const [items, setItems] = useState<Entry[]>([]);
  const [name, setName] = useState('');
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/guestbook?limit=100`);
      setItems(await r.json());
      setMsg('');
    } catch {
      setMsg('방명록을 불러오지 못했어요.');
    }
    setLoading(false);
  }, []);

  useEffect(() => { if (visible) load(); }, [visible, load]);

  const submit = async () => {
    if (!text.trim() || sending) return;
    setSending(true);
    try {
      const r = await fetch(`${API}/api/guestbook`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim(), text: text.trim() }),
      });
      if (r.status === 429) setMsg('조금 뒤에 다시 써주세요.');
      else if (!r.ok) setMsg('등록에 실패했어요.');
      else { setText(''); const e: Entry = await r.json(); setItems(p => [e, ...p]); setMsg(''); }
    } catch {
      setMsg('서버에 연결할 수 없어요.');
    }
    setSending(false);
  };

  return (
    <Modal visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={s.sheetWrap}>
        <View style={s.sheet}>
          <View style={s.row}>
            <Text style={s.title}>방명록</Text>
            <Pressable onPress={onClose}><Text style={s.sub}>닫기 ✕</Text></Pressable>
          </View>
          <TextInput style={s.input} placeholder="닉네임 (선택)" placeholderTextColor={C.sub}
            maxLength={20} value={name} onChangeText={setName} />
          <TextInput style={[s.input, { height: 64 }]} placeholder="한마디 남겨주세요 (140자)" placeholderTextColor={C.sub}
            maxLength={140} multiline value={text} onChangeText={setText} />
          <Pressable style={[s.btn, sending && { opacity: .5 }]} onPress={submit}>
            <Text style={s.btnText}>{sending ? '등록 중...' : '등록'}</Text>
          </Pressable>
          {!!msg && <Text style={s.sub}>{msg}</Text>}
          {loading ? <ActivityIndicator color={C.accent} style={{ marginTop: 16 }} /> : (
            <FlatList
              data={items}
              keyExtractor={e => String(e.id)}
              style={{ marginTop: 12 }}
              ListEmptyComponent={<Text style={s.sub}>첫 방명록을 남겨보세요!</Text>}
              renderItem={({ item }) => (
                <View style={s.entry}>
                  <Text>
                    <Text style={s.name}>{item.name || '익명'}</Text>
                    <Text style={s.time}>  {new Date(item.created_at).toLocaleString('ko-KR')}</Text>
                  </Text>
                  <Text style={s.text}>{item.text}</Text>
                </View>
              )}
            />
          )}
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

export default function App() {
  const [open, setOpen] = useState(false);
  const { width, height } = useWindowDimensions();
  const playerW = Math.min(width, height * 9 / 16);

  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="light" />
      <View style={{ flex: 1, width: playerW, alignSelf: 'center' }}>
        <Player />
      </View>
      <Pressable style={s.fab} onPress={() => setOpen(true)}>
        <Text style={s.btnText}>📝 방명록</Text>
      </Pressable>
      <Guestbook visible={open} onClose={() => setOpen(false)} />
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  fab: { position: 'absolute', right: 16, bottom: 24, backgroundColor: C.accent, paddingVertical: 10, paddingHorizontal: 18, borderRadius: 999 },
  sheetWrap: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(0,0,0,.4)' },
  sheet: { height: '70%', backgroundColor: '#0a0d11', borderTopLeftRadius: 16, borderTopRightRadius: 16, padding: 16, gap: 8, width: '100%', maxWidth: 560, alignSelf: 'center' },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 },
  title: { color: C.accent, fontSize: 17, fontWeight: '700' },
  sub: { color: C.sub, fontSize: 13 },
  input: { backgroundColor: C.card, borderColor: C.line, borderWidth: 1, borderRadius: 8, color: C.text, padding: 10, fontSize: 14 },
  btn: { alignSelf: 'flex-end', backgroundColor: C.accent, paddingVertical: 9, paddingHorizontal: 22, borderRadius: 999 },
  btnText: { color: '#07120d', fontWeight: '700', fontSize: 14 },
  entry: { backgroundColor: C.card, borderRadius: 8, padding: 10, marginBottom: 8 },
  name: { color: C.accent, fontWeight: '700' },
  time: { color: '#5a646e', fontSize: 12 },
  text: { color: C.text, marginTop: 4, fontSize: 14 },
});
