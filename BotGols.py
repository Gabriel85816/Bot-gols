# bot_gols_playwright_1tempo_minuto_corrigido.py
import time
import random
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
import os

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]

def send_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Enviado ao Telegram.")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro ao enviar (status {r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro ao enviar mensagem: {e}")

def parse_int(value):
    if not value:
        return 0
    try:
        value_clean = ''.join(filter(str.isdigit, str(value)))
        return int(value_clean)
    except:
        return 0

def analyze_match(event, stats_data):
    try:
        home = event['homeTeam']['name']
        away = event['awayTeam']['name']
        tournament = event['tournament']['name']
        score_home = parse_int(event['homeScore'].get('current'))
        score_away = parse_int(event['awayScore'].get('current'))
        minute_display = parse_int(event['time'].get('current'))

        # Só analisar se o jogo estiver 0x0 e no 1º tempo
        if score_home != 0 or score_away != 0 or minute_display > 45:
            return None

        # Corrigir minuto caso venha 0 (intervalo)
        if minute_display == 0:
            minute_display = 45

        shots_on_goal = 0
        total_shots = 0
        corners = 0

        for stat in stats_data.get('statistics', []):
            for group in stat.get('groups', []):
                for item in group.get('statisticsItems', []):
                    name = item.get('name', '').lower()
                    h = parse_int(item.get('home'))
                    a = parse_int(item.get('away'))
                    total = h + a
                    if 'shots on target' in name or 'chutes no gol' in name:
                        shots_on_goal = total
                    elif 'total shots' in name or 'finalizações' in name:
                        total_shots = total
                    elif 'corner' in name or 'escanteio' in name:
                        corners = total

        # Chance de over 0.5 gol 1º tempo
        chance = None
        if shots_on_goal >= 5 and total_shots >= 9 and corners >= 4:
            chance = "🔥 Alta chance de gol no 1º tempo"
        elif shots_on_goal >= 3 and total_shots >= 6 and corners >= 2:
            chance = "⚽ Média chance de gol no 1º tempo"

        if not chance:
            return None

        message = (
            f"<b>{tournament}</b>\n"
            f"⚽ {home} {score_home}x{score_away} {away}\n"
            f"⏱️ Minuto: {minute_display}'\n"
            f"{chance}"
        )
        return message
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro analyze_match: {e}")
        return None

def run_bot():
    sent_alerts = set()
    print(f"\n{'='*60}")
    print(f"🟢 Bot Playwright iniciado às {datetime.now().strftime('%H:%M:%S')} — abrindo navegador...")
    print(f"{'='*60}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(user_agent=random.choice(USER_AGENTS), locale="pt-BR")
        page = context.new_page()

        try:
            page.goto("https://www.sofascore.com/football", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🌐 Página inicial carregada, sessão criada.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro ao abrir sofascore: {e}")

        try:
            while True:
                start_time = datetime.now().strftime('%H:%M:%S')
                try:
                    script = """
                        async () => {
                            const resp = await fetch('https://www.sofascore.com/api/v1/sport/football/events/live', { credentials: 'include' });
                            return await resp.json();
                        }
                    """
                    result = page.evaluate(script)
                    events = result.get('events', []) if isinstance(result, dict) else []
                except Exception as e:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro fetching events: {e}")
                    events = []

                if not events:
                    print(f"[{start_time}] ⚙️ Nenhuma partida ao vivo encontrada.")
                else:
                    print(f"[{start_time}] 📊 {len(events)} partidas ao vivo encontradas. Analisando...")

                for match in events:
                    event_id = match.get('id')
                    if not event_id or event_id in sent_alerts:
                        continue

                    try:
                        stats_script = f"""
                            async () => {{
                                const resp = await fetch('https://www.sofascore.com/api/v1/event/{event_id}/statistics', {{ credentials: 'include' }});
                                return await resp.json();
                            }}
                        """
                        stats = page.evaluate(stats_script)
                    except Exception as e:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Erro fetch stats {event_id}: {e}")
                        stats = None

                    if stats:
                        message = analyze_match(match, stats)
                        if message:
                            send_to_telegram(message)
                            sent_alerts.add(event_id)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 🚨 Alerta gerado para {match['homeTeam']['name']} x {match['awayTeam']['name']}")
                        else:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ {match['homeTeam']['name']} x {match['awayTeam']['name']} — sem chance clara.")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Sem estatísticas para {match['homeTeam']['name']} x {match['awayTeam']['name']}")

                print(f"[{datetime.now().strftime('%H:%M:%S')}] 💚 Aguardando 60 segundos para próxima verificação...\n")
                time.sleep(60)

        except KeyboardInterrupt:
            print("\n🛑 Execução interrompida manualmente. Encerrando...")
        finally:
            try:
                context.close()
                browser.close()
            except:
                pass

if __name__ == "__main__":
    run_bot()
