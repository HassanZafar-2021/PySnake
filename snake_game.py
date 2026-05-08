import pygame
import time
import random
import math
import struct
import wave
import io
import os

# ── Window & Speed ────────────────────────────────────────────────────────────
WINDOW_X, WINDOW_Y = 800, 600
CELL = 20
BASE_SPEED = 8
MAX_SPEED  = 22

# ── Palette ───────────────────────────────────────────────────────────────────
BLACK      = pygame.Color(0,   0,   0)
WHITE      = pygame.Color(255, 255, 255)
RED        = pygame.Color(220,  50,  50)
GREEN      = pygame.Color( 50, 220,  80)
DARK_GREEN = pygame.Color( 20,  80,  30)
GOLD       = pygame.Color(255, 215,   0)
CYAN       = pygame.Color(  0, 240, 255)
PURPLE     = pygame.Color(160,  32, 240)
ORANGE     = pygame.Color(255, 140,   0)
BG_DARK    = pygame.Color( 10,  12,  20)
BG_GRID    = pygame.Color( 15,  18,  30)
OBSTACLE   = pygame.Color(180,  60,  60)

pygame.init()
pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)


# ── Procedural chiptune ───────────────────────────────────────────────────────
def make_tone(freq, duration, volume=0.25, wave_type="square"):
    sample_rate = 44100
    n_samples   = int(sample_rate * duration)
    buf = []
    for i in range(n_samples):
        t = i / sample_rate
        if wave_type == "square":
            val = 1.0 if math.sin(2 * math.pi * freq * t) > 0 else -1.0
        elif wave_type == "triangle":
            val = 2 * abs(2 * (t * freq - math.floor(t * freq + 0.5))) - 1
        else:
            val = math.sin(2 * math.pi * freq * t)
        fade = min(1.0, min(i, n_samples - i) / (sample_rate * 0.01))
        buf.append(int(val * volume * fade * 32767))
    raw = struct.pack(f"{n_samples}h", *buf)
    buf_io = io.BytesIO()
    with wave.open(buf_io, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    buf_io.seek(0)
    return pygame.mixer.Sound(buf_io)

# Simple chiptune melody (frequencies + durations)
MELODY = [
    (330, 0.12), (392, 0.12), (494, 0.12), (523, 0.24),
    (392, 0.12), (440, 0.12), (494, 0.24), (330, 0.12),
    (392, 0.12), (523, 0.12), (587, 0.24), (523, 0.12),
    (494, 0.12), (440, 0.12), (392, 0.24), (330, 0.12),
]

melody_sounds = [make_tone(f, d, wave_type="square") for f, d in MELODY]
eat_sound     = make_tone(880, 0.08, wave_type="triangle")
die_sound     = make_tone(110, 0.4,  wave_type="square")

music_index  = 0
music_timer  = 0.0
music_active = True

def tick_music(dt):
    global music_index, music_timer
    if not music_active:
        return
    music_timer -= dt
    if music_timer <= 0:
        snd = melody_sounds[music_index % len(melody_sounds)]
        snd.play()
        music_timer = MELODY[music_index % len(MELODY)][1]
        music_index += 1


# ── Rainbow snake colours ─────────────────────────────────────────────────────
def rainbow(index, total):
    hue = (index / max(total, 1)) * 360
    h = hue / 60
    x = 1 - abs(h % 2 - 1)
    r, g, b = [(1,x,0),(x,1,0),(0,1,x),(0,x,1),(x,0,1),(1,0,x)][int(h) % 6]
    return pygame.Color(int(r*220)+35, int(g*220)+35, int(b*220)+35)


# ── Particles ─────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y):
        self.x  = x + CELL // 2
        self.y  = y + CELL // 2
        angle   = random.uniform(0, 2 * math.pi)
        speed   = random.uniform(60, 180)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life    = 1.0
        self.decay   = random.uniform(1.5, 3.0)
        self.size    = random.randint(3, 7)
        self.color   = random.choice([GOLD, CYAN, ORANGE, WHITE, GREEN])

    def update(self, dt):
        self.x    += self.vx * dt
        self.y    += self.vy * dt
        self.vy   += 150 * dt   # gravity
        self.life -= self.decay * dt

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = max(0, int(self.life * 255))
        c = pygame.Color(self.color.r, self.color.g, self.color.b, alpha)
        pygame.draw.circle(surface, c, (int(self.x), int(self.y)), self.size)


# ── Score pop-ups ──────────────────────────────────────────────────────────────
class ScorePop:
    def __init__(self, x, y, text):
        self.x    = x
        self.y    = float(y)
        self.text = text
        self.life = 1.2
        self.font = pygame.font.SysFont("couriernew", 22, bold=True)

    def update(self, dt):
        self.y    -= 60 * dt
        self.life -= dt

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = max(0, int((self.life / 1.2) * 255))
        surf = self.font.render(self.text, True, GOLD)
        surf.set_alpha(alpha)
        surface.blit(surf, (self.x, int(self.y)))


# ── Background grid ───────────────────────────────────────────────────────────
def draw_bg(surface):
    surface.fill(BG_DARK)
    for x in range(0, WINDOW_X, CELL):
        pygame.draw.line(surface, BG_GRID, (x, 0), (x, WINDOW_Y))
    for y in range(0, WINDOW_Y, CELL):
        pygame.draw.line(surface, BG_GRID, (0, y), (WINDOW_X, y))


# ── Pulsing fruit ─────────────────────────────────────────────────────────────
def draw_fruit(surface, pos, t):
    cx = pos[0] + CELL // 2
    cy = pos[1] + CELL // 2
    pulse = int(4 * math.sin(t * 5))
    # glow rings
    for r, alpha in [(14+pulse, 40), (10+pulse//2, 80)]:
        glow = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(glow, (255, 80, 80, alpha), (r, r), r)
        surface.blit(glow, (cx - r, cy - r))
    pygame.draw.circle(surface, RED,    (cx, cy), 8)
    pygame.draw.circle(surface, ORANGE, (cx-2, cy-2), 3)


# ── HUD ───────────────────────────────────────────────────────────────────────
hud_font   = pygame.font.SysFont("couriernew", 22, bold=True)
small_font = pygame.font.SysFont("couriernew", 16)

def draw_hud(surface, score, level, mode, time_left=None):
    # Score
    s = hud_font.render(f"SCORE: {score}", True, WHITE)
    surface.blit(s, (10, 8))
    # Level
    lv = hud_font.render(f"LVL {level}", True, CYAN)
    surface.blit(lv, (WINDOW_X//2 - lv.get_width()//2, 8))
    # Mode tag
    tag = small_font.render("◆ CHALLENGE" if mode == "challenge" else "◆ NORMAL", True, ORANGE if mode == "challenge" else GREEN)
    surface.blit(tag, (WINDOW_X - tag.get_width() - 10, 8))
    # Timer for challenge mode
    if time_left is not None:
        color = RED if time_left < 10 else WHITE
        tm = hud_font.render(f"⏱ {int(time_left)}s", True, color)
        surface.blit(tm, (WINDOW_X//2 - tm.get_width()//2, 34))
        # bar
        bar_w = 200
        ratio = max(0, time_left / 60.0)
        pygame.draw.rect(surface, (60, 60, 60), (WINDOW_X//2 - bar_w//2, 56, bar_w, 8), border_radius=4)
        pygame.draw.rect(surface, color,        (WINDOW_X//2 - bar_w//2, 56, int(bar_w * ratio), 8), border_radius=4)


# ── Obstacle set ──────────────────────────────────────────────────────────────
def generate_obstacles(count, snake_body, fruit_pos):
    occupied = set(map(tuple, snake_body)) | {tuple(fruit_pos)}
    obs = []
    attempts = 0
    while len(obs) < count and attempts < 500:
        attempts += 1
        x = random.randrange(0, WINDOW_X // CELL) * CELL
        y = random.randrange(2, WINDOW_Y // CELL) * CELL   # keep top rows clear
        if (x, y) not in occupied:
            occupied.add((x, y))
            obs.append([x, y])
    return obs

def draw_obstacles(surface, obstacles, t):
    for obs in obstacles:
        shade = int(180 + 30 * math.sin(t * 3 + obs[0] * 0.1))
        col   = pygame.Color(shade, 50, 50)
        pygame.draw.rect(surface, col, pygame.Rect(obs[0]+1, obs[1]+1, CELL-2, CELL-2), border_radius=3)
        pygame.draw.rect(surface, pygame.Color(255, 100, 100), pygame.Rect(obs[0]+1, obs[1]+1, CELL-2, CELL-2), 1, border_radius=3)


# ── Main menu ─────────────────────────────────────────────────────────────────
def main_menu(surface):
    title_font  = pygame.font.SysFont("couriernew", 62, bold=True)
    option_font = pygame.font.SysFont("couriernew", 30, bold=True)
    hint_font   = pygame.font.SysFont("couriernew", 18)
    clock       = pygame.time.Clock()
    t           = 0.0
    selected    = 0   # 0 = normal, 1 = challenge

    snake_demo  = [[200 - i*CELL, 300] for i in range(8)]
    demo_dir    = [CELL, 0]
    demo_timer  = 0.0

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); quit()
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    selected ^= 1
                if event.key == pygame.K_RETURN:
                    return "normal" if selected == 0 else "challenge"
            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = pygame.mouse.get_pos()
                if 230 <= my <= 280:
                    return "normal"
                if 310 <= my <= 360:
                    return "challenge"

        # Demo snake wander
        demo_timer += dt
        if demo_timer > 0.18:
            demo_timer = 0
            if random.random() < 0.3:
                choices = [[CELL,0],[-CELL,0],[0,CELL],[0,-CELL]]
                choices = [d for d in choices if d != [-demo_dir[0], -demo_dir[1]]]
                demo_dir = random.choice(choices)
            head = [snake_demo[0][0]+demo_dir[0], snake_demo[0][1]+demo_dir[1]]
            head[0] %= WINDOW_X
            head[1]  = max(80, head[1] % WINDOW_Y)
            snake_demo.insert(0, head)
            snake_demo.pop()

        draw_bg(surface)

        # Animated title
        colors = [rainbow(i + int(t*6), 10) for i in range(10)]
        title  = "SNAKE"
        tx     = WINDOW_X//2 - title_font.size(title)[0]//2
        for i, ch in enumerate(title):
            bounce = int(8 * math.sin(t * 4 + i * 0.8))
            cs = title_font.render(ch, True, colors[i % len(colors)])
            surface.blit(cs, (tx + i * title_font.size(ch)[0], 55 + bounce))

        # Demo snake
        for i, seg in enumerate(snake_demo):
            pygame.draw.rect(surface, rainbow(i, len(snake_demo)),
                             pygame.Rect(seg[0]+1, seg[1]+1, CELL-2, CELL-2), border_radius=4)

        # Menu options
        opts   = ["▶  NORMAL MODE", "▶  CHALLENGE MODE"]
        descs  = ["Classic snake — avoid walls & yourself",
                  "Obstacles appear & time ticks down!"]
        for i, (opt, desc) in enumerate(zip(opts, descs)):
            y     = 240 + i * 80
            bg_c  = (30, 60, 30) if (i == selected) else (20, 20, 30)
            brd_c = GREEN if (i == selected) else (60, 60, 80)
            pygame.draw.rect(surface, bg_c,  (WINDOW_X//2-220, y-10, 440, 60), border_radius=8)
            pygame.draw.rect(surface, brd_c, (WINDOW_X//2-220, y-10, 440, 60), 2, border_radius=8)
            col  = WHITE if i == selected else pygame.Color(140,140,160)
            txt  = option_font.render(opt, True, col)
            surface.blit(txt, (WINDOW_X//2 - txt.get_width()//2, y))
            dtxt = hint_font.render(desc, True, pygame.Color(120,120,140))
            surface.blit(dtxt, (WINDOW_X//2 - dtxt.get_width()//2, y+32))

        # Footer hint
        hint = hint_font.render("↑↓ to select   ENTER to start   arrow keys to steer", True, pygame.Color(80,80,100))
        surface.blit(hint, (WINDOW_X//2 - hint.get_width()//2, WINDOW_Y - 30))

        tick_music(dt)
        pygame.display.update()


# ── Game over screen ──────────────────────────────────────────────────────────
def game_over_screen(surface, score, mode):
    die_sound.play()
    big_font   = pygame.font.SysFont("couriernew", 54, bold=True)
    med_font   = pygame.font.SysFont("couriernew", 28, bold=True)
    small_font2= pygame.font.SysFont("couriernew", 20)
    clock      = pygame.time.Clock()
    t          = 0.0

    btn_w, btn_h = 180, 52
    retry_r = pygame.Rect(WINDOW_X//2 - btn_w - 20, WINDOW_Y//2 + 60, btn_w, btn_h)
    menu_r  = pygame.Rect(WINDOW_X//2 + 20,          WINDOW_Y//2 + 60, btn_w, btn_h)

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return "retry"
                if event.key == pygame.K_m:
                    return "menu"
            if event.type == pygame.MOUSEBUTTONDOWN:
                mp = pygame.mouse.get_pos()
                if retry_r.collidepoint(mp): return "retry"
                if menu_r.collidepoint(mp):  return "menu"

        draw_bg(surface)

        # Pulsing "GAME OVER"
        pulse = 1.0 + 0.04 * math.sin(t * 6)
        go_surf = big_font.render("GAME OVER", True, RED)
        scaled  = pygame.transform.scale(go_surf, (int(go_surf.get_width()*pulse), int(go_surf.get_height()*pulse)))
        surface.blit(scaled, (WINDOW_X//2 - scaled.get_width()//2, WINDOW_Y//4 - 20))

        sc_surf = med_font.render(f"SCORE: {score}", True, GOLD)
        surface.blit(sc_surf, (WINDOW_X//2 - sc_surf.get_width()//2, WINDOW_Y//4 + 70))

        # Buttons
        for rect, label, color in [(retry_r, "RETRY  [R]", GREEN), (menu_r, "MENU  [M]", CYAN)]:
            hover = rect.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(surface, (40, 80, 40) if hover else (20, 40, 20), rect, border_radius=8)
            pygame.draw.rect(surface, color, rect, 2, border_radius=8)
            bt = med_font.render(label, True, color)
            surface.blit(bt, (rect.x + rect.w//2 - bt.get_width()//2, rect.y + rect.h//2 - bt.get_height()//2))

        hint = small_font2.render("press R to retry or M for menu", True, pygame.Color(80,80,100))
        surface.blit(hint, (WINDOW_X//2 - hint.get_width()//2, WINDOW_Y - 30))

        tick_music(dt)
        pygame.display.update()


# ── Core game loop ────────────────────────────────────────────────────────────
def run_game(surface, mode):
    global music_index, music_timer

    clock = pygame.time.Clock()

    # State
    snake_pos  = [CELL * 5, CELL * 5]
    snake_body = [[CELL * 5 - i * CELL, CELL * 5] for i in range(4)]
    direction  = "RIGHT"
    change_to  = "RIGHT"
    score      = 0
    level      = 1
    t          = 0.0
    particles  = []
    pops       = []

    # Fruit
    def new_fruit():
        while True:
            fx = random.randrange(0, WINDOW_X // CELL) * CELL
            fy = random.randrange(3, WINDOW_Y // CELL) * CELL
            if [fx, fy] not in snake_body:
                return [fx, fy]

    fruit_pos  = new_fruit()

    # Obstacles
    obstacles   = []
    obs_timer   = 0.0          # how often to add new obstacle in challenge
    time_left   = 60.0         # challenge mode countdown

    if mode == "challenge":
        obstacles = generate_obstacles(5, snake_body, fruit_pos)

    speed          = BASE_SPEED
    move_acc       = 0.0       # fractional accumulator for smooth speed control
    frame_duration = 1.0 / speed

    while True:
        dt = clock.tick(60) / 1000.0
        t += dt

        # ── Events ────────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP    and direction != "DOWN":  change_to = "UP"
                if event.key == pygame.K_DOWN  and direction != "UP":    change_to = "DOWN"
                if event.key == pygame.K_LEFT  and direction != "RIGHT": change_to = "LEFT"
                if event.key == pygame.K_RIGHT and direction != "LEFT":  change_to = "RIGHT"

        direction = change_to

        # ── Move accumulator (speed-independent) ──────────────────────────────
        move_acc += dt
        moved     = False
        if move_acc >= frame_duration:
            move_acc -= frame_duration
            moved     = True

        if moved:
            deltas = {"UP":(0,-CELL),"DOWN":(0,CELL),"LEFT":(-CELL,0),"RIGHT":(CELL,0)}
            dx, dy = deltas[direction]
            snake_pos = [snake_pos[0] + dx, snake_pos[1] + dy]
            snake_body.insert(0, list(snake_pos))

            # Eat?
            if snake_pos == fruit_pos:
                score    += 10
                level     = score // 50 + 1
                speed     = min(MAX_SPEED, BASE_SPEED + level - 1)
                frame_duration = 1.0 / speed
                eat_sound.play()
                # Particles
                for _ in range(18):
                    particles.append(Particle(fruit_pos[0], fruit_pos[1]))
                pops.append(ScorePop(fruit_pos[0], fruit_pos[1] - 10, f"+10"))
                fruit_pos = new_fruit()
                # New obstacle in challenge
                if mode == "challenge" and random.random() < 0.5:
                    new_obs = generate_obstacles(1, snake_body, fruit_pos)
                    obstacles.extend(new_obs)
            else:
                snake_body.pop()

            # ── Collision ─────────────────────────────────────────────────────
            # Wall
            if snake_pos[0] < 0 or snake_pos[0] >= WINDOW_X or \
               snake_pos[1] < 0 or snake_pos[1] >= WINDOW_Y:
                return game_over_screen(surface, score, mode)
            # Self
            if snake_pos in snake_body[1:]:
                return game_over_screen(surface, score, mode)
            # Obstacles
            if any(snake_pos == obs for obs in obstacles):
                return game_over_screen(surface, score, mode)

        # ── Challenge timer ───────────────────────────────────────────────────
        if mode == "challenge":
            time_left -= dt
            if time_left <= 0:
                return game_over_screen(surface, score, mode)

        # ── Particles & pops ──────────────────────────────────────────────────
        for p in particles[:]:
            p.update(dt)
            if p.life <= 0:
                particles.remove(p)
        for pop in pops[:]:
            pop.update(dt)
            if pop.life <= 0:
                pops.remove(pop)

        # ── Draw ──────────────────────────────────────────────────────────────
        draw_bg(surface)
        draw_obstacles(surface, obstacles, t)
        draw_fruit(surface, fruit_pos, t)

        # Rainbow snake
        for i, seg in enumerate(snake_body):
            col = rainbow(i, len(snake_body))
            if i == 0:  # head is brighter
                pygame.draw.rect(surface, WHITE,
                                 pygame.Rect(seg[0], seg[1], CELL, CELL), border_radius=5)
                pygame.draw.rect(surface, col,
                                 pygame.Rect(seg[0]+2, seg[1]+2, CELL-4, CELL-4), border_radius=4)
            else:
                pygame.draw.rect(surface, col,
                                 pygame.Rect(seg[0]+1, seg[1]+1, CELL-2, CELL-2), border_radius=4)

        for p in particles:
            p.draw(surface)
        for pop in pops:
            pop.draw(surface)

        draw_hud(surface, score, level, mode, time_left if mode == "challenge" else None)
        tick_music(dt)
        pygame.display.update()


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    surface = pygame.display.set_mode((WINDOW_X, WINDOW_Y))
    pygame.display.set_caption("🐍 SNAKE — HYPER EDITION")

    while True:
        mode   = main_menu(surface)
        result = run_game(surface, mode)
        while result in ("retry",):
            result = run_game(surface, mode)
        # result == "menu" → loop back to main_menu

if __name__ == "__main__":
    main()