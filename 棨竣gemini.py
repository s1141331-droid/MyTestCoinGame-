import pygame
import sys
import random
import os
import math

# --- 初始化 Pygame ---
pygame.init()

# --- 遊戲設定 ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("接金幣遊戲 (雷射特效美化版)")

# --- 顏色定義 (RGB) ---
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
GRAY = (100, 100, 100)
BLUE = (50, 50, 200)
GOLD = (255, 215, 0)
DARK_GRAY = (30, 30, 30)
RED = (255, 0, 0)
SHIELD_COLOR = (100, 200, 255, 180) 
BLOCK_COLOR = (50, 50, 50, 150)
LASER_RED = (255, 50, 50)   
LASER_GLOW = (255, 150, 150, 150)
WARNING_COLOR = (255, 0, 0, 80)    
SPIKE_COLOR = (150, 150, 150)      
SPIKE_DARK = (60, 60, 60)
SPIKE_GLOW = (255, 100, 100)

# --- 全域常數 ---
PLAYER_SPEED = 7
COIN_SPEED = 5
NORMAL_COIN_FREQUENCY = 45 
PENALTY_COIN_FREQUENCY = 1  
GRAVITY = 0.8       
JUMP_STRENGTH = -15 

# --- 資源管理器 ---
class ResourceManager:
    def __init__(self):
        self.assets = {}
        self.load_assets()

    def load_assets(self):
        asset_path = "assets"
        if not os.path.exists(asset_path):
            return
        valid_extensions = (".png", ".jpg", ".jpeg")
        for filename in os.listdir(asset_path):
            if filename.lower().endswith(valid_extensions):
                name = os.path.splitext(filename)[0]
                full_path = os.path.join(asset_path, filename)
                try:
                    self.assets[name] = pygame.image.load(full_path).convert_alpha()
                except pygame.error:
                    pass

    def get(self, name):
        return self.assets.get(name)

resource_manager = ResourceManager()

# --- 遊戲狀態 ---
score = 0
is_in_penalty_mode = False 
has_cleared_penalty = False 
penalty_timer = 0 
PENALTY_DURATION = 300 
is_dead = False 
death_timer = 0 

def get_font(size, bold=False):
    fonts = ['SimHei', 'Microsoft JhengHei', 'Arial Unicode MS', 'Arial']
    for f in fonts:
        try:
            return pygame.font.SysFont(f, size, bold)
        except:
            continue
    return pygame.font.SysFont(None, size)

font = get_font(36) 
big_font = get_font(72, True)
shop_font = get_font(22) 
clock = pygame.time.Clock()

# --- 子彈類別 ---
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, target_x, target_y):
        super().__init__()
        self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(self.image, RED, (12, 12), 12)
        pygame.draw.circle(self.image, WHITE, (12, 12), 6)
        self.rect = self.image.get_rect(center=(x, y))
        
        angle = math.atan2(target_y - y, target_x - x)
        self.speed = 6
        self.vx = math.cos(angle) * self.speed
        self.vy = math.sin(angle) * self.speed

    def update(self):
        self.rect.x += self.vx
        self.rect.y += self.vy
        if self.rect.top > SCREEN_HEIGHT or self.rect.bottom < 0 or \
           self.rect.left > SCREEN_WIDTH or self.rect.right < 0:
            self.kill()

# --- 空中敵人類別 ---
class AerialEnemy(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.base_size = 200 
        img = resource_manager.get('player_jump')
        if img:
            self.image = pygame.transform.scale(img, (self.base_size, self.base_size))
        else:
            self.image = pygame.Surface((self.base_size, self.base_size), pygame.SRCALPHA)
            pygame.draw.rect(self.image, RED, (0, 0, self.base_size, self.base_size), border_radius=15)
            pygame.draw.circle(self.image, WHITE, (self.base_size//2, self.base_size//2), self.base_size//3)
        
        self.rect = self.image.get_rect()
        self.rect.y = 20
        self.rect.x = -self.rect.width
        self.speed = 4
        self.direction = 1 
        self.shoot_cooldown = 120 
        self.timer = 0
        self.active = False

    def update(self, player_hitbox, current_score, bullet_group, all_group):
        if current_score >= 3000:
            self.active = True
        else:
            self.active = False
            return

        self.rect.x += self.speed * self.direction
        if self.rect.right >= SCREEN_WIDTH:
            self.direction = -1
        elif self.rect.left <= 0:
            self.direction = 1

        self.timer += 1
        if self.timer >= self.shoot_cooldown:
            self.timer = 0
            b = Bullet(self.rect.centerx, self.rect.centery, player_hitbox.centerx, player_hitbox.centery)
            bullet_group.add(b)
            all_group.add(b)

    def draw(self, surface):
        if self.active:
            surface.blit(self.image, self.rect)

# --- 雷射炮管理系統 (美化版) ---
class LaserCannon:
    def __init__(self, unlock_score=2000):
        self.active = False
        self.unlock_score = unlock_score
        self.cooldown = 300  
        self.timer = random.randint(0, 100)
        self.warning_duration = 120 
        self.fire_duration = 40      
        self.width = 140            
        self.x = 0                  
        self.is_firing = False
        self.is_warning = False
        self.energy_particles = [] # 預警時的匯聚粒子

    def update(self, current_score):
        if current_score >= self.unlock_score:
            self.active = True
        else:
            self.active = False
            self.reset_cycle()
            return

        self.timer += 1
        cycle_time = self.timer % self.cooldown
        
        if cycle_time == 1:
            self.x = random.randint(0, SCREEN_WIDTH - self.width)
            self.is_warning = True
            self.is_firing = False
            self.energy_particles = []
        elif cycle_time == self.warning_duration:
            self.is_warning = False
            self.is_firing = True
        elif cycle_time == self.warning_duration + self.fire_duration:
            self.is_firing = False
            
        if self.is_warning:
            # 產生能量匯聚粒子特效
            if len(self.energy_particles) < 20:
                px = self.x + random.randint(0, self.width)
                py = random.randint(50, 150)
                self.energy_particles.append({'x': px, 'y': py, 'life': 1.0})
            
            for p in self.energy_particles[:]:
                p['y'] -= 2 # 向上移動
                p['life'] -= 0.02
                if p['life'] <= 0:
                    self.energy_particles.remove(p)

    def check_collision(self, target_hitbox, shield_active, shield_rect):
        if self.is_firing:
            laser_rect = pygame.Rect(self.x + 20, 0, self.width - 40, SCREEN_HEIGHT)
            if shield_active:
                if laser_rect.colliderect(shield_rect):
                    return False
            return laser_rect.colliderect(target_hitbox)
        return False

    def draw(self, surface):
        if not self.active:
            return
        
        # 繪製雷射炮台本體
        cannon_body = pygame.Rect(self.x, 0, self.width, 35)
        pygame.draw.rect(surface, (40, 40, 50), cannon_body, border_bottom_left_radius=10, border_bottom_right_radius=10)
        pygame.draw.rect(surface, GRAY, cannon_body, 2, border_bottom_left_radius=10, border_bottom_right_radius=10)
        
        # 繪製核心能量球
        core_color = RED if self.is_warning else (255, 255, 255)
        if self.is_firing: core_color = (255, 255, 200)
        pygame.draw.circle(surface, core_color, (self.x + self.width // 2, 15), 8)

        if self.is_warning:
            # 1. 預警掃描線
            warn_alpha = abs(math.sin(self.timer * 0.1)) * 60 + 20
            warn_surf = pygame.Surface((self.width, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(warn_surf, (255, 0, 0, int(warn_alpha)), (0, 0, self.width, SCREEN_HEIGHT))
            surface.blit(warn_surf, (self.x, 0))
            
            # 2. 邊界閃爍線
            if (self.timer // 15) % 2 == 0:
                pygame.draw.line(surface, RED, (self.x, 0), (self.x, SCREEN_HEIGHT), 2)
                pygame.draw.line(surface, RED, (self.x + self.width, 0), (self.x + self.width, SCREEN_HEIGHT), 2)

            # 3. 匯聚粒子
            for p in self.energy_particles:
                p_alpha = int(p['life'] * 255)
                pygame.draw.circle(surface, (255, 50, 50, p_alpha), (p['x'], p['y']), 3)

        if self.is_firing:
            # 1. 外層大發光 (柔和邊緣)
            glow_w = self.width - 20
            glow_surf = pygame.Surface((glow_w, SCREEN_HEIGHT), pygame.SRCALPHA)
            for i in range(5): # 多層漸層
                alpha = 100 - (i * 20)
                offset = i * 4
                pygame.draw.rect(glow_surf, (255, 0, 0, alpha), (offset, 0, glow_w - offset*2, SCREEN_HEIGHT))
            surface.blit(glow_surf, (self.x + 10, 0))
            
            # 2. 主雷射束 (中間最亮)
            main_beam_w = 40 + math.sin(self.timer * 0.5) * 10 # 粗細震盪感
            main_beam_x = self.x + (self.width - main_beam_w) // 2
            pygame.draw.rect(surface, LASER_RED, (main_beam_x, 0, main_beam_w, SCREEN_HEIGHT))
            
            # 3. 核心白光 (視覺衝擊感)
            core_beam_w = main_beam_w * 0.4
            core_beam_x = self.x + (self.width - core_beam_w) // 2
            pygame.draw.rect(surface, WHITE, (core_beam_x, 0, core_beam_w, SCREEN_HEIGHT))
            
            # 4. 底部火花特效
            for _ in range(5):
                spark_x = random.randint(int(self.x), int(self.x + self.width))
                spark_y = random.randint(SCREEN_HEIGHT - 30, SCREEN_HEIGHT)
                pygame.draw.circle(surface, YELLOW, (spark_x, spark_y), random.randint(2, 4))

    def reset_cycle(self):
        self.timer = random.randint(0, 100)
        self.is_firing = False
        self.is_warning = False
        self.energy_particles = []

# --- 地底尖刺系統 (強化版特效) ---
class GroundSpikes:
    def __init__(self):
        self.active = False
        self.cooldown = 180  
        self.timer = 0
        self.warning_duration = 60  
        self.attack_duration = 40   
        self.width = 300            
        self.height = 120           
        self.x = 0
        self.is_attacking = False
        self.is_warning = False
        # 視覺特效變數
        self.anim_frame = 0

    def update(self, current_score):
        if current_score >= 2500:
            self.active = True
        else:
            self.active = False
            self.reset_cycle()
            return

        self.timer += 1
        cycle_time = self.timer % self.cooldown

        if cycle_time == 1:
            self.x = random.randint(0, SCREEN_WIDTH - self.width)
            self.is_warning = True
            self.is_attacking = False
            self.anim_frame = 0
        elif cycle_time == self.warning_duration:
            self.is_warning = False
            self.is_attacking = True
            self.anim_frame = 0 # 重置動畫幀供攻擊使用
        elif cycle_time == self.warning_duration + self.attack_duration:
            self.is_attacking = False

        if self.is_attacking or self.is_warning:
            self.anim_frame += 1

    def check_collision(self, target_hitbox):
        if self.is_attacking:
            spike_rect = pygame.Rect(self.x, SCREEN_HEIGHT - self.height, self.width, self.height)
            return spike_rect.colliderect(target_hitbox)
        return False

    def draw(self, surface):
        if not self.active:
            return
        
        if self.is_warning:
            shake_x = random.randint(-2, 2)
            warn_alpha = abs(math.sin(self.anim_frame * 0.2)) * 150 + 50
            warn_surf = pygame.Surface((self.width, 15), pygame.SRCALPHA)
            pygame.draw.rect(warn_surf, (255, 0, 0, int(warn_alpha)), (0, 0, self.width, 15))
            surface.blit(warn_surf, (self.x + shake_x, SCREEN_HEIGHT - 15))
            
            for _ in range(3):
                px = random.randint(self.x, self.x + self.width)
                py = random.randint(SCREEN_HEIGHT - 20, SCREEN_HEIGHT)
                pygame.draw.circle(surface, RED, (px, py), random.randint(1, 3))

        if self.is_attacking:
            rise_ratio = min(1.0, self.anim_frame / 6.0)
            current_h = self.height * rise_ratio
            
            num_spikes = 6
            spike_w = self.width // num_spikes
            
            for i in range(num_spikes):
                base_x = self.x + (i * spike_w)
                points_side = [
                    (base_x, SCREEN_HEIGHT),
                    (base_x + spike_w // 2, SCREEN_HEIGHT - current_h),
                    (base_x + spike_w * 0.7, SCREEN_HEIGHT)
                ]
                pygame.draw.polygon(surface, SPIKE_DARK, points_side)
                
                points_main = [
                    (base_x + 5, SCREEN_HEIGHT),
                    (base_x + spike_w // 2, SCREEN_HEIGHT - current_h),
                    (base_x + spike_w - 5, SCREEN_HEIGHT)
                ]
                pygame.draw.polygon(surface, SPIKE_COLOR, points_main)
                
                if rise_ratio > 0.8:
                    tip_pos = (base_x + spike_w // 2, SCREEN_HEIGHT - current_h)
                    pygame.draw.circle(surface, WHITE, tip_pos, 3)
                
                pygame.draw.polygon(surface, WHITE, points_main, 1)

            glow_surf = pygame.Surface((self.width, 20), pygame.SRCALPHA)
            pygame.draw.rect(glow_surf, (255, 50, 0, 100), (0, 0, self.width, 20), border_radius=10)
            surface.blit(glow_surf, (self.x, SCREEN_HEIGHT - 10))

    def reset_cycle(self):
        self.timer = 0
        self.is_attacking = False
        self.is_warning = False
        self.anim_frame = 0

laser_cannons = [LaserCannon(2000), LaserCannon(4000)]
ground_spikes = GroundSpikes()
aerial_enemy = AerialEnemy()
bullets = pygame.sprite.Group()

# --- 角色選擇介面 ---
class CharacterSelector:
    def __init__(self):
        self.selected_base = "player"
        self.options = ["player", "player2"] 
        self.is_active = True
        self.option_rects = []
        for i in range(len(self.options)):
            rect = pygame.Rect(150 + i * 300, 250, 200, 200)
            self.option_rects.append(rect)

    def draw(self, surface):
        surface.fill(DARK_GRAY)
        title = font.render("Choose Your Character", True, WHITE)
        surface.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        for i, option in enumerate(self.options):
            rect = self.option_rects[i]
            color = GOLD if self.selected_base == option else WHITE
            pygame.draw.rect(surface, color, rect, 5, border_radius=10)
            char_img = resource_manager.get(option)
            if char_img:
                scaled_img = pygame.transform.scale(char_img, (180, 180))
                surface.blit(scaled_img, (rect.x + 10, rect.y + 10))
            else:
                pygame.draw.circle(surface, GRAY, rect.center, 60)
                txt = shop_font.render(option, True, WHITE)
                surface.blit(txt, (rect.centerx - txt.get_width()//2, rect.bottom + 10))
        
        self.start_btn = pygame.Rect(300, 500, 200, 60)
        pygame.draw.rect(surface, BLUE, self.start_btn, border_radius=10)
        start_txt = font.render("START", True, WHITE)
        surface.blit(start_txt, (self.start_btn.centerx - start_txt.get_width()//2, self.start_btn.centery - start_txt.get_height()//2))

    def handle_click(self, pos):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(pos):
                self.selected_base = self.options[i]
                return
        if self.start_btn.collidepoint(pos):
            self.is_active = False

selector = CharacterSelector()

# --- 商店類別 ---
class Shop:
    def __init__(self):
        self.is_open = False
        self.items = [
            {"name": "提升速度 (Speed Up)", "cost": 500, "type": "speed"},
            {"name": "強力跳躍 (High Jump)", "cost": 800, "type": "jump"},
            {"name": "終極護盾 (Shield x1) [X]", "cost": 1000, "type": "shield"},
            {"name": "格擋系統 (BLOCK) [F]", "cost": 1200, "type": "block_skill"}
        ]
        self.rect = pygame.Rect(150, 50, 500, 500) 
        self.close_button = pygame.Rect(600, 60, 40, 40)
        self.double_score_active = False
        self.shield_count = 0
        self.has_block_skill = False

    def draw(self, surface):
        if not self.is_open:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, BLUE, self.rect, border_radius=15)
        pygame.draw.rect(surface, WHITE, self.rect, 3, border_radius=15)
        title = font.render("Item Shop", True, GOLD)
        surface.blit(title, (self.rect.centerx - title.get_width()//2, self.rect.y + 20))
        
        hint = shop_font.render("[ Press F to use BLOCK ]", True, WHITE)
        surface.blit(hint, (self.rect.centerx - hint.get_width()//2, self.rect.y + 55))

        pygame.draw.rect(surface, (200, 0, 0), self.close_button)
        close_text = shop_font.render("X", True, WHITE)
        surface.blit(close_text, (self.close_button.centerx - 10, self.close_button.centery - 12))
        
        for i, item in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x + 50, self.rect.y + 100 + (i * 85), 400, 70)
            pygame.draw.rect(surface, GRAY, item_rect, border_radius=10)
            
            display_name = item['name']
            if item['type'] == "block_skill" and self.has_block_skill:
                display_name += " (OWNED)"
                
            name_text = shop_font.render(f"{display_name}", True, WHITE)
            cost_text = shop_font.render(f"Cost: {item['cost']}", True, YELLOW)
            surface.blit(name_text, (item_rect.x + 20, item_rect.y + 10))
            surface.blit(cost_text, (item_rect.x + 20, item_rect.y + 40))

    def handle_click(self, pos, current_player):
        global score
        if not self.is_open: return False
        if self.close_button.collidepoint(pos):
            self.is_open = False
            return True
        for i, item in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x + 50, self.rect.y + 100 + (i * 85), 400, 70)
            if item_rect.collidepoint(pos):
                if score >= item['cost']:
                    if item['type'] == "block_skill" and self.has_block_skill:
                        continue
                    score -= item['cost']
                    self.apply_item(item['type'], current_player)
                return True
        return False

    def apply_item(self, item_type, current_player):
        if item_type == "speed": current_player.speed += 2
        elif item_type == "jump": current_player.jump_strength -= 3
        elif item_type == "shield": self.shield_count += 1
        elif item_type == "block_skill": self.has_block_skill = True

    def reset(self):
        self.double_score_active = False
        self.shield_count = 0
        self.has_block_skill = False

shop = Shop()

# --- 玩家類別 ---
class Player(pygame.sprite.Sprite):
    def __init__(self, base_character):
        super().__init__()
        self.base_name = base_character 
        self.speed = PLAYER_SPEED
        self.jump_strength = JUMP_STRENGTH
        self.velocity_y = 0
        self.gravity = GRAVITY
        self.is_jumping = False 
        self.level = 1 
        
        self.shield_active = False
        self.shield_timer = 0
        self.shield_duration = 300 
        self.shield_width = 500 
        self.shield_height = 40
        self.shield_rect = pygame.Rect(0, 0, self.shield_width, self.shield_height)
        
        self.is_blocking = False
        self.current_size = 200 
        self.load_player_images()
        self.image = self.idle_img
        self.rect = self.image.get_rect()
        
        self.hit_rect = self.rect.inflate(-self.rect.width * 0.75, -self.rect.height * 0.4)
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 10 
        self.ground_y = self.rect.bottom
        self.hit_rect.center = self.rect.center

    def reset_stats(self):
        self.speed = PLAYER_SPEED
        self.jump_strength = JUMP_STRENGTH
        self.level = 1
        self.shield_active = False
        self.is_blocking = False
        self.load_player_images()

    def load_player_images(self):
        global is_in_penalty_mode
        if is_in_penalty_mode or self.level >= 2:
            idle_name, jump_name = self.base_name + '2', self.base_name + '2_jump'
        else:
            idle_name, jump_name = self.base_name, self.base_name + '_jump'
        
        idle_res = resource_manager.get(idle_name)
        jump_res = resource_manager.get(jump_name)
        if not idle_res: idle_res = resource_manager.get(self.base_name)
        if not jump_res: jump_res = idle_res
        
        if idle_res:
            self.idle_img = pygame.transform.scale(idle_res, (self.current_size, self.current_size))
        else:
            self.idle_img = pygame.Surface([self.current_size, self.current_size], pygame.SRCALPHA)
            color = WHITE if self.level == 1 else (0, 255, 0)
            pygame.draw.rect(self.idle_img, color, (20, 20, self.current_size-40, self.current_size-40), border_radius=20)
            
        if jump_res:
            self.jump_img = pygame.transform.scale(jump_res, (self.current_size, self.current_size))
        else:
            self.jump_img = self.idle_img.copy()

    def check_evolution(self, current_score):
        global is_in_penalty_mode, penalty_timer, score, is_dead, death_timer, has_cleared_penalty
        state_changed = False
        
        if current_score < 0 and not is_dead:
            self.trigger_death()
            return

        if current_score >= 1500 and not is_in_penalty_mode and not has_cleared_penalty:
            is_in_penalty_mode = True
            penalty_timer = PENALTY_DURATION
            state_changed = True
        
        if is_in_penalty_mode:
            penalty_timer -= 1
            if penalty_timer <= 0:
                is_in_penalty_mode = False
                has_cleared_penalty = True 
                self.level = 1
                state_changed = True
        
        if not is_in_penalty_mode and not is_dead:
            if self.level == 1 and current_score >= 100:
                self.level = 2
                state_changed = True

        if state_changed:
            self.load_player_images()
            old_center = self.rect.center
            self.image = self.jump_img if self.is_jumping else self.idle_img
            new_rect = self.image.get_rect()
            new_rect.center = old_center
            self.rect = new_rect
            self.hit_rect = self.rect.inflate(-self.rect.width * 0.75, -self.rect.height * 0.4)

    def trigger_death(self):
        global is_dead, death_timer
        if not is_dead:
            is_dead = True
            death_timer = 120

    def jump(self):
        if not self.is_jumping and not self.is_blocking:
            self.velocity_y = self.jump_strength
            self.is_jumping = True
            self.image = self.jump_img 

    def activate_shield(self):
        if shop.shield_count > 0 and not self.shield_active:
            shop.shield_count -= 1
            self.shield_active = True
            self.shield_timer = self.shield_duration

    def update(self):
        keys = pygame.key.get_pressed()
        
        if keys[pygame.K_f] and shop.has_block_skill:
            self.is_blocking = True
        else:
            self.is_blocking = False

        move_speed = self.speed
        if self.is_blocking:
            move_speed = 2
        
        if keys[pygame.K_LEFT]: self.rect.x -= move_speed
        if keys[pygame.K_RIGHT]: self.rect.x += move_speed
        
        self.velocity_y += self.gravity
        self.rect.y += self.velocity_y
        
        if self.shield_active:
            self.shield_rect.centerx = self.rect.centerx
            self.shield_rect.bottom = self.rect.top - 10
            self.shield_timer -= 1
            if self.shield_timer <= 0:
                self.shield_active = False

        if self.rect.bottom >= self.ground_y:
            self.rect.bottom = self.ground_y
            self.velocity_y = 0
            if self.is_jumping:
                self.is_jumping, self.image = False, self.idle_img 
        
        self.hit_rect.center = self.rect.center
        
        if self.hit_rect.left < 0:
            self.rect.left -= self.hit_rect.left
            self.hit_rect.left = 0
        if self.hit_rect.right > SCREEN_WIDTH:
            self.rect.right -= (self.hit_rect.right - SCREEN_WIDTH)
            self.hit_rect.right = SCREEN_WIDTH

    def draw_shield(self, surface):
        if self.shield_active:
            shield_surf = pygame.Surface((self.shield_width, self.shield_height), pygame.SRCALPHA)
            pygame.draw.rect(shield_surf, SHIELD_COLOR, (0, 0, self.shield_width, self.shield_height), border_radius=15)
            pygame.draw.rect(shield_surf, WHITE, (0, 0, self.shield_width, self.shield_height), 2, border_radius=15)
            surface.blit(shield_surf, self.shield_rect.topleft)
        
        if self.is_blocking:
            block_surf = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
            pygame.draw.circle(block_surf, (255, 255, 255, 80), (self.rect.width//2, self.rect.height//2), 100, 10)
            surface.blit(block_surf, self.rect.topleft)

# --- 金幣類別 ---
class Coin(pygame.sprite.Sprite):
    def __init__(self, current_score):
        super().__init__()
        global is_in_penalty_mode, has_cleared_penalty
        self.type = "normal" 
        
        if is_in_penalty_mode:
            size, hit, asset, self.type = 180, 100, 'flag3', "penalty"
        elif has_cleared_penalty:
            size, hit, asset = 80, 70, 'flag'
        elif current_score >= 500:
            size, hit, asset = 120, 100, 'player_jump' 
        elif current_score >= 100:
            size, hit, asset = 90, 80, 'flag2' 
        else:
            size, hit, asset = 70, 60, 'flag'
            
        self.speed = COIN_SPEED
        img = resource_manager.get(asset)
        if img: 
            self.image = pygame.transform.scale(img, (size, size))
        else:
            self.image = pygame.Surface([size, size], pygame.SRCALPHA)
            c = RED if self.type == "penalty" else GOLD
            pygame.draw.circle(self.image, c, (size//2, size//2), size//2)
            pygame.draw.circle(self.image, WHITE, (size//2, size//2), size//2, 3)
        
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(0, SCREEN_WIDTH - self.rect.width)
        self.rect.y = -self.rect.height
        self.hit_rect = pygame.Rect(0, 0, hit, hit)

    def update(self):
        self.rect.y += self.speed
        self.hit_rect.center = self.rect.center

# --- 遊戲控制變數 ---
all_sprites = pygame.sprite.Group() 
coins = pygame.sprite.Group()
player = None

def spawn_coin():
    c = Coin(score)
    all_sprites.add(c)
    coins.add(c)

def reset_game():
    global score, is_in_penalty_mode, penalty_timer, is_dead, has_cleared_penalty, player
    score = 0
    is_in_penalty_mode = False
    has_cleared_penalty = False
    penalty_timer = 0
    is_dead = False
    for lc in laser_cannons: lc.reset_cycle()
    ground_spikes.reset_cycle()
    for sprite in all_sprites: sprite.kill()
    bullets.empty()
    if player: 
        player = Player(selector.selected_base)
        all_sprites.add(player)
    shop.reset()

# --- 主遊戲迴圈 ---
running = True
coin_counter = 0

while running:
    if selector.is_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.MOUSEBUTTONDOWN:
                selector.handle_click(event.pos)
        selector.draw(screen)
        if not selector.is_active:
            player = Player(selector.selected_base)
            all_sprites.add(player)
            
    else:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if not is_dead:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE: player.jump()
                    if event.key == pygame.K_x: player.activate_shield()
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if pygame.Rect(0, 0, 250, 150).collidepoint(event.pos):
                        shop.is_open = not shop.is_open
                    else:
                        shop.handle_click(event.pos, player)

        if not shop.is_open and not is_dead:
            player.check_evolution(score) 
            for lc in laser_cannons:
                lc.update(score)
            ground_spikes.update(score)
            aerial_enemy.update(player.hit_rect, score, bullets, all_sprites)
            
            for lc in laser_cannons:
                if lc.check_collision(player.hit_rect, player.shield_active, player.shield_rect):
                    player.trigger_death()
            
            if ground_spikes.check_collision(player.hit_rect):
                player.trigger_death()
            
            for bullet in bullets:
                if player.shield_active and player.shield_rect.colliderect(bullet.rect):
                    bullet.kill()
                elif player.is_blocking and player.hit_rect.colliderect(bullet.rect):
                    bullet.kill()
                elif player.hit_rect.colliderect(bullet.rect):
                    player.trigger_death()

            all_sprites.update()
            coin_counter += 1
            
            freq = PENALTY_COIN_FREQUENCY if is_in_penalty_mode else NORMAL_COIN_FREQUENCY
            if coin_counter % freq == 0: spawn_coin()
            
            for coin in list(coins):
                if coin.rect.top > SCREEN_HEIGHT:
                    if not is_in_penalty_mode and coin.type == "normal": score -= 5
                    coin.kill()
                elif player.shield_active and player.shield_rect.colliderect(coin.hit_rect):
                    coin.kill()
                elif player.is_blocking and player.hit_rect.colliderect(coin.hit_rect):
                    coin.kill()
                elif player.hit_rect.colliderect(coin.hit_rect):
                    val = -100 if coin.type == "penalty" else 100
                    if shop.double_score_active and val > 0: val *= 2
                    score += val
                    coin.kill()
        
        if is_dead:
            death_timer -= 1
            if death_timer <= 0:
                reset_game()

        screen.fill(BLACK) 
        all_sprites.draw(screen)
        aerial_enemy.draw(screen)

        if player:
            player.draw_shield(screen)
        
        for lc in laser_cannons:
            lc.draw(screen)
        ground_spikes.draw(screen)
        
        score_area = pygame.Rect(10, 10, 260, 140)
        pygame.draw.rect(screen, DARK_GRAY, score_area, border_radius=10)
        pygame.draw.rect(screen, WHITE, score_area, 2, border_radius=10)
        
        score_text = font.render(f"Credits: {score}", True, WHITE)
        screen.blit(score_text, (20, 15))
        
        if is_in_penalty_mode:
            timer_sec = max(0, penalty_timer // 60 + 1)
            time_text = shop_font.render(f"DANGER: {timer_sec}s", True, RED)
            screen.blit(time_text, (20, 50))
        
        shield_text = shop_font.render(f"Shields: {shop.shield_count} (X)", True, BLUE if shop.shield_count > 0 else GRAY)
        screen.blit(shield_text, (20, 75))
        
        block_status_color = YELLOW if shop.has_block_skill else GRAY
        block_text = shop_font.render(f"BLOCK: {'READY (F)' if shop.has_block_skill else 'NOT OWNED'}", True, block_status_color)
        screen.blit(block_text, (20, 100))

        shop_hint = shop_font.render("(Click to Shop)", True, GOLD)
        screen.blit(shop_hint, (20, 122))

        if is_dead:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((150, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            death_msg = big_font.render("GAME OVER", True, WHITE)
            hint_msg = font.render("You are such a failure", True, YELLOW)
            screen.blit(death_msg, (SCREEN_WIDTH//2 - death_msg.get_width()//2, SCREEN_HEIGHT//2 - 50))
            screen.blit(hint_msg, (SCREEN_WIDTH//2 - hint_msg.get_width()//2, SCREEN_HEIGHT//2 + 40))
        
        shop.draw(screen)
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()