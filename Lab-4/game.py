import math
import random

import pygame

WIDTH, HEIGHT = 800, 560
FPS = 60
BG = (30, 35, 25)
HUD_HEIGHT = 62
HIT_GRACE_MS = 1200
CLIP_SIZE = 12
RELOAD_MS = 2000
BLAST_RADIUS = 115
BLAST_MS = 400


class Zombie:
    SPEED = 1.5
    SIZE = 30
    HP = 3
    COLOR = (60, 140, 60)

    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, self.SIZE, self.SIZE)
        self.position = pygame.Vector2(self.rect.center)
        self.hp = self.HP
        self.frame = 0

    def update(self, player_pos):
        offset = pygame.Vector2(player_pos) - self.position
        if offset:
            self.position += offset.normalize() * min(self.SPEED, offset.length())
            self.rect.center = round(self.position.x), round(self.position.y)
        self.frame += 1

    def hit(self):
        self.hp -= 1
        return self.hp <= 0

    def draw(self, screen):
        wobble_y = int(math.sin(self.frame*0.2)*3)
        draw_rect = self.rect.move(0, wobble_y)
        pygame.draw.rect(screen, self.COLOR, draw_rect, border_radius=5)
        for fraction in (1 / 3, 2 / 3):
            eye = (draw_rect.x + int(self.SIZE * fraction), draw_rect.y + self.SIZE // 3)
            pygame.draw.circle(screen, (200, 40, 40), eye, 3)


class FastZombie(Zombie):
    SPEED = 2.75
    SIZE = 20
    HP = 1
    COLOR = (192, 180, 55)


class TankZombie(Zombie):
    SPEED = 0.85
    SIZE = 46
    HP = 6
    COLOR = (148, 86, 169)


def spawn_zombie(width, height, player_rect, zombie_type=Zombie, margin=120):
    size = zombie_type.SIZE
    exclusion = player_rect.inflate(margin, margin)
    while True:
        x = random.randint(0, width - size)
        y = random.randint(HUD_HEIGHT, height - size)
        if not pygame.Rect(x, y, size, size).colliderect(exclusion):
            return zombie_type(x, y)


SPEED = 4


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, 32, 32)
        self.color = (60,160,220)
        self.bullets = []
        self.shoot_cooldown = 0
        self.hp = 3
        self.invincible_until = 0
        self.ammo = CLIP_SIZE
        self.reload_until = None

    def take_hit(self, now):
        if now >= self.invincible_until and self.hp > 0:
            self.hp -= 1
            self.invincible_until = now + HIT_GRACE_MS

    def update_reload(self, now):
        if self.reload_until is not None and now >= self.reload_until:
            self.ammo = CLIP_SIZE
            self.reload_until = None

    def move(self, keys, width, height):
        dx = dy = 0
        if keys[pygame.K_w] or keys[pygame.K_UP]: dy = -SPEED
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: dy = SPEED
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: dx = -SPEED
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: dx = SPEED
        self.rect.x = max(0, min(width-self.rect.width, self.rect.x+dx))
        self.rect.y = max(HUD_HEIGHT, min(height-self.rect.height, self.rect.y+dy))
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= 1

    def shoot(self, target_pos, now):
        self.update_reload(now)
        if self.shoot_cooldown > 0 or self.ammo == 0:
            return
        origin = pygame.Vector2(self.rect.center)
        direction = pygame.Vector2(target_pos) - origin
        if not direction:
            return
        self.bullets.append((origin, direction.normalize() * 10))
        self.shoot_cooldown = 15
        self.ammo -= 1
        if self.ammo == 0:
            self.reload_until = now + RELOAD_MS

    def update_bullets(self, width, height):
        for position, velocity in self.bullets:
            position.update(position + velocity)
        self.bullets = [
            bullet for bullet in self.bullets
            if 0 <= bullet[0].x < width and HUD_HEIGHT <= bullet[0].y < height
        ]

    def draw(self, screen, now):
        flashing = now < self.invincible_until and (self.invincible_until - now) // 90 % 2
        color = (245, 245, 255) if flashing else self.color
        pygame.draw.rect(screen, color, self.rect, border_radius=6)
        for position, _ in self.bullets:
            pygame.draw.circle(screen, (255, 220, 60), position, 5)


class GameEngine:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Zombie Escape")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("monospace", 19)
        self.big_font = pygame.font.SysFont("monospace", 44, bold=True)
        self.reset()

    def reset(self):
        self.player = Player(WIDTH//2, HEIGHT//2)
        self.barrels = [
            pygame.Rect(x - 13, y - 16, 26, 32)
            for x, y in ((180, 180), (620, 180), (180, 440), (620, 440))
        ]
        self.blasts = []
        self.score = 0
        self.wave = 1
        self.kills = 0
        self.kills_to_next = 8
        self.game_over = False
        self.start_time = pygame.time.get_ticks()
        self.total_kills = 0
        self.spawn_wave()

    def spawn_wave(self):
        zombie_types = [FastZombie, TankZombie] + [Zombie] * (self.kills_to_next - 2)
        self.zombies = [
            spawn_zombie(WIDTH, HEIGHT, self.player.rect, zombie_type)
            for zombie_type in zombie_types
        ]

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r: self.reset()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not self.game_over:
                self.player.shoot(event.pos, pygame.time.get_ticks())
        return True

    def update(self):
        if self.game_over:
            return
        now = pygame.time.get_ticks()
        self.player.move(pygame.key.get_pressed(), WIDTH, HEIGHT)
        self.player.update_reload(now)
        self.player.update_bullets(WIDTH, HEIGHT)
        self.blasts = [(center, end) for center, end in self.blasts if end > now]

        for zombie in self.zombies:
            zombie.update(self.player.rect.center)
            if zombie.rect.colliderect(self.player.rect):
                self.player.take_hit(now)
        self.game_over = self.player.hp == 0

        remaining_bullets = []
        for bullet in self.player.bullets:
            position, _ = bullet
            barrel = next((item for item in self.barrels if item.collidepoint(position)), None)
            if barrel is not None:
                self.explode(barrel, now)
                continue
            zombie = next((item for item in self.zombies if item.rect.collidepoint(position)), None)
            if zombie is None:
                remaining_bullets.append(bullet)
            elif zombie.hit():
                self.zombies.remove(zombie)
                self.kills += 1
        self.player.bullets = remaining_bullets

        self.score = (now - self.start_time) // 1000 + (self.total_kills + self.kills) * 10
        if not self.zombies and not self.game_over:
            self.total_kills += self.kills
            self.kills = 0
            self.wave += 1
            self.kills_to_next = 8 + self.wave * 2
            self.spawn_wave()

    def explode(self, barrel, now):
        center = pygame.Vector2(barrel.center)
        self.barrels.remove(barrel)
        self.blasts.append((center, now + BLAST_MS))
        survivors = [
            zombie for zombie in self.zombies
            if center.distance_squared_to(zombie.rect.center) > BLAST_RADIUS ** 2
        ]
        self.kills += len(self.zombies) - len(survivors)
        self.zombies = survivors

    def draw(self):
        self.screen.fill(BG)
        for x in range(0, WIDTH, 60):
            pygame.draw.line(self.screen, (40,45,35), (x,0), (x,HEIGHT), 1)
        for y in range(0, HEIGHT, 60):
            pygame.draw.line(self.screen, (40,45,35), (0,y), (WIDTH,y), 1)
        now = pygame.time.get_ticks()
        for barrel in self.barrels:
            pygame.draw.rect(self.screen, (160, 61, 43), barrel, border_radius=5)
            pygame.draw.rect(self.screen, (255, 188, 84), barrel.inflate(-2, -17))
        for zombie in self.zombies:
            zombie.draw(self.screen)
        self.player.draw(self.screen, now)
        for center, end in self.blasts:
            progress = 1 - max(0, end - now) / BLAST_MS
            radius = max(4, int(BLAST_RADIUS * (0.3 + 0.7 * progress)))
            pygame.draw.circle(self.screen, (255, 153, 53), center, radius, 5)
            pygame.draw.circle(self.screen, (255, 221, 133), center, radius // 2, 3)

        pygame.draw.rect(self.screen, (15, 20, 15), (0, 0, WIDTH, HUD_HEIGHT))
        reload_until = self.player.reload_until
        ammo = f"Ammo {self.player.ammo}/{CLIP_SIZE}"
        if reload_until is not None:
            seconds = max(0, reload_until - now) / 1000
            ammo += f"  Reload {seconds:.1f}s"
        status = (
            f"Wave {self.wave}   Score {self.score}   "
            f"Kills {self.kills}/{self.kills_to_next}   HP {self.player.hp}/3   {ammo}"
        )
        self.screen.blit(self.font.render(status, True, (160, 220, 120)), (8, 5))
        controls = "WASD / Arrows: Move   Left click: Shoot   R: Restart"
        self.screen.blit(self.font.render(controls, True, (200, 210, 195)), (8, 32))
        if self.game_over:
            ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            ov.fill((0,0,0,160))
            self.screen.blit(ov, (0,0))
            m = self.big_font.render("DEVOURED!", True, (180,40,40))
            s = self.font.render(f"Wave {self.wave} | Score {self.score} | Press R", True, (200,200,200))
            self.screen.blit(m, (WIDTH//2-m.get_width()//2, HEIGHT//2-40))
            self.screen.blit(s, (WIDTH//2-s.get_width()//2, HEIGHT//2+20))
        pygame.display.flip()

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    engine = GameEngine()
    engine.run()
