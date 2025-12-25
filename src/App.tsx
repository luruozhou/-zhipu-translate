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
  const [usageLoading, setUsageLoading] = useState(false);
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
    const { data: { session }, error } = await supabase.auth.getSession();
    if (error || !session) {
      setUsage(null);
      return;
    }

    setUsageLoading(true);
    try {
      const res = await axios.get<Usage>('/api/me/usage', {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      setUsage(res.data);
      setError(null);
    } catch (e: any) {
      console.error('获取用量信息失败:', e);
      setUsage(null);
      // 不设置 error，因为用量信息获取失败不应该影响其他功能
    } finally {
      setUsageLoading(false);
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
        '/api/translate',
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
          </>
        )}
      </section>

      {userEmail && (
        <section style={{ 
          marginBottom: 24, 
          border: '1px solid #e0e0e0', 
          padding: 20,
          borderRadius: '8px',
          backgroundColor: '#f9f9f9'
        }}>
          <h2 style={{ margin: '0 0 16px 0', fontSize: '20px', color: '#1a1a1a' }}>
            我的用量信息
          </h2>
          
          {usageLoading ? (
            <p style={{ color: '#666', margin: 0 }}>加载中...</p>
          ) : usage ? (
            <>
              <div style={{ marginBottom: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span style={{ fontSize: '14px', color: '#666' }}>使用进度</span>
                  <span style={{ fontSize: '14px', fontWeight: 500, color: '#1a1a1a' }}>
                    {((usage.used_tokens_this_period / usage.monthly_quota_tokens) * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{
                  width: '100%',
                  height: '24px',
                  backgroundColor: '#e0e0e0',
                  borderRadius: '12px',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    width: `${Math.min(100, (usage.used_tokens_this_period / usage.monthly_quota_tokens) * 100)}%`,
                    height: '100%',
                    backgroundColor: (usage.used_tokens_this_period / usage.monthly_quota_tokens) > 0.8 
                      ? '#ff4444' 
                      : (usage.used_tokens_this_period / usage.monthly_quota_tokens) > 0.5 
                        ? '#ffaa00' 
                        : '#4CAF50',
                    transition: 'width 0.3s ease',
                    borderRadius: '12px'
                  }} />
                </div>
              </div>

              <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
                gap: '12px' 
              }}>
                <div style={{ padding: '12px', backgroundColor: 'white', borderRadius: '6px' }}>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#666' }}>月度配额</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#1a1a1a' }}>
                    {usage.monthly_quota_tokens.toLocaleString()}
                  </p>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#999' }}>tokens</p>
                </div>
                <div style={{ padding: '12px', backgroundColor: 'white', borderRadius: '6px' }}>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#666' }}>已使用</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#ff4444' }}>
                    {usage.used_tokens_this_period.toLocaleString()}
                  </p>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#999' }}>tokens</p>
                </div>
                <div style={{ padding: '12px', backgroundColor: 'white', borderRadius: '6px' }}>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#666' }}>剩余额度</p>
                  <p style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#4CAF50' }}>
                    {usage.remaining_tokens.toLocaleString()}
                  </p>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#999' }}>tokens</p>
                </div>
                <div style={{ padding: '12px', backgroundColor: 'white', borderRadius: '6px' }}>
                  <p style={{ margin: '0 0 4px 0', fontSize: '12px', color: '#666' }}>计费周期</p>
                  <p style={{ margin: 0, fontSize: '14px', fontWeight: 500, color: '#1a1a1a' }}>
                    {new Date(usage.billing_period_start).toLocaleDateString('zh-CN')}
                  </p>
                  <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#999' }}>开始日期</p>
                </div>
              </div>
            </>
          ) : (
            <p style={{ color: '#999', margin: 0 }}>暂无用量信息</p>
          )}
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


