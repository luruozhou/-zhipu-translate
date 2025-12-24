import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { supabase } from './lib/supabaseClient';

declare global {
  interface Window {
    google?: any;
  }
}

type Usage = {
  monthly_quota_tokens: number;
  used_tokens_this_period: number;
  billing_period_start: string;
  remaining_tokens: number;
};

type TranslateResp = {
  translated_text: string;
  estimated_tokens: number;
  remaining_tokens: number;
};

const GOOGLE_CLIENT_ID =
  '699759489682-emo2kip9mcso80dinpatdor4h6ohm82r.apps.googleusercontent.com';

async function loadGsiScript() {
  if (document.getElementById('google-identity-services')) return;

  await new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.id = 'google-identity-services';
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error('加载 Google 登录脚本失败'));
    document.head.appendChild(script);
  });
}

const GoogleSignIn: React.FC<{ onError: (msg: string) => void }> = ({
  onError,
}) => {
  const buttonRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        await loadGsiScript();
        if (cancelled) return;

        if (!window.google?.accounts?.id) {
          throw new Error('Google 身份服务初始化失败');
        }

        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: async (response: any) => {
            try {
              const credential = response.credential;
              if (!credential) {
                throw new Error('未获取到 Google 凭证');
              }

              const { error } = await supabase.auth.signInWithIdToken({
                provider: 'google',
                token: credential,
              });
              if (error) throw error;
              // 登录成功后，App 里监听到 session 变化会自动更新 UI
            } catch (e: any) {
              console.error('GSI 登录错误:', e);
              onError(e.message || '登录失败，请稍后重试');
            }
          },
          ux_mode: 'popup',
          context: 'signin',
          auto_select: true,
          itp_support: true,
          use_fedcm_for_prompt: false,
        });

        if (buttonRef.current) {
          window.google.accounts.id.renderButton(buttonRef.current, {
            type: 'standard',
            shape: 'pill',
            theme: 'outline',
            text: 'signin_with',
            size: 'large',
            logo_alignment: 'left',
          });
        }

        // 触发 One Tap / FedCM 提示
        window.google.accounts.id.prompt();
      } catch (e: any) {
        console.error(e);
        onError(e.message || '初始化 Google 登录失败');
      }
    }

    init();

    return () => {
      cancelled = true;
      try {
        window.google?.accounts?.id?.cancel();
      } catch {
        // ignore
      }
    };
  }, [onError]);

  return <div ref={buttonRef} />;
};

const App: React.FC = () => {
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [text, setText] = useState('');
  const [targetLang, setTargetLang] = useState('英文');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session?.user) {
        setUserEmail(data.session.user.email ?? null);
        fetchUsage();
      }
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      if (session?.user) {
        setUserEmail(session.user.email ?? null);
        fetchUsage();
      } else {
        setUserEmail(null);
        setUsage(null);
      }
    });

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  async function loginWithGoogle() {
    setError(null);
    try {
      await loadGsiScript();
      if (!window.google?.accounts?.id) {
        throw new Error('Google 身份服务初始化失败');
      }
      // 手动触发 FedCM / One Tap 提示作为备用方式
      window.google.accounts.id.prompt();
    } catch (e: any) {
      console.error(e);
      setError(e.message || '启动 Google 登录失败');
    }
  }

  async function logout() {
    await supabase.auth.signOut();
  }

  async function fetchUsage() {
    try {
      const { data: { session }, error } = await supabase.auth.getSession();
      if (error || !session) return;

      const res = await axios.get<Usage>('http://localhost:8000/me/usage', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setUsage(res.data);
    } catch (e: any) {
      console.error(e);
    }
  }

  async function handleTranslate() {
    setError(null);
    setLoading(true);
    setResult('');
    try {
      const { data: { session }, error } = await supabase.auth.getSession();
      if (error || !session) throw new Error('请先登录');

      const res = await axios.post<TranslateResp>(
        'http://localhost:8000/translate',
        { text, target_lang: targetLang },
        {
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      setResult(res.data.translated_text);
      setUsage(prev =>
        prev
          ? {
              ...prev,
              remaining_tokens: res.data.remaining_tokens,
              used_tokens_this_period:
                prev.monthly_quota_tokens - res.data.remaining_tokens,
            }
          : prev
      );
    } catch (e: any) {
      console.error(e);
      setError(e.response?.data?.detail || e.message || '翻译失败');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', fontFamily: 'system-ui' }}>
      <h1>会员翻译系统</h1>

      <section style={{ marginBottom: 24 }}>
        {userEmail ? (
          <>
            <p>已登录：{userEmail}</p>
            <button onClick={logout}>退出登录</button>
          </>
        ) : (
          <>
            <GoogleSignIn onError={msg => setError(msg)} />
            <div style={{ marginTop: 8 }}>
              <button onClick={loginWithGoogle}>如果按钮未出现，点击这里尝试登录</button>
            </div>
          </>
        )}
      </section>

      {usage && (
        <section style={{ marginBottom: 24, border: '1px solid #eee', padding: 16 }}>
          <h2>本月用量</h2>
          <p>配额：{usage.monthly_quota_tokens} tokens</p>
          <p>已用：{usage.used_tokens_this_period} tokens</p>
          <p>剩余：{usage.remaining_tokens} tokens</p>
          <p>周期开始：{usage.billing_period_start}</p>
        </section>
      )}

      <section style={{ marginBottom: 16 }}>
        <label>目标语言：</label>
        <select
          value={targetLang}
          onChange={e => setTargetLang(e.target.value)}
        >
          <option value="英文">英文</option>
          <option value="中文">中文</option>
          <option value="日文">日文</option>
        </select>
      </section>

      <section style={{ marginBottom: 16 }}>
        <textarea
          rows={6}
          style={{ width: '100%' }}
          placeholder="输入需要翻译的文本"
          value={text}
          onChange={e => setText(e.target.value)}
        />
      </section>

      <button onClick={handleTranslate} disabled={loading || !userEmail}>
        {loading ? '翻译中...' : '开始翻译并计费'}
      </button>

      {error && <p style={{ color: 'red', marginTop: 12 }}>{error}</p>}

      {result && (
        <section style={{ marginTop: 24 }}>
          <h2>翻译结果</h2>
          <pre>{result}</pre>
        </section>
      )}
    </div>
  );
};

export default App;


