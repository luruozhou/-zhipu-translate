import { createClient } from '@supabase/supabase-js';

// TODO: 替换为你自己的 anon 公钥
const SUPABASE_URL = 'https://bdxgeqvzvcnlsldlvnum.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkeGdlcXZ6dmNubHNsZGx2bnVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY0MzY0MzMsImV4cCI6MjA4MjAxMjQzM30.AetYNUKsYfye6VB3a8_zAQCaYPohvv0IyniMsORt3xM';

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);


