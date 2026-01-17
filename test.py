import pygame
import sys
import random
import os
import math

# ==========================================
# --- 初始化與核心設定 ---
# ==========================================
pygame.init()

# 視窗尺寸
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("接金幣遊戲 - 終極強化版 (包含閃現與進階挑戰)")

# 顏色常數定義
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

# 遊戲平衡參數
PLAYER_SPEED = 7
COIN_SPEED = 5
NORMAL_COIN_FREQUENCY = 45 
PENALTY_COIN_FREQUENCY = 1  
GRAVITY = 0.8       
JUMP_STRENGTH = -15 

# ==========================================
# --- 資源管理器 (負責載入圖片) ---
# ==========================================
class ResourceManager:
    """負責統一管理遊戲中所有的圖片資源，若找不到檔案則提供替代方案"""
    def __init__(self):
        self.assets = {}
        self.load_assets()

    def load_assets(self):
        asset_path = "assets"
        if not os.path.exists(asset_path):
            print(f"警告: 找不到 {asset_path} 目錄，將使用幾何圖形代替圖片。")
            return
        valid_extensions = (".png", ".jpg", ".jpeg")
        for filename in os.listdir(asset_path):
            if filename.lower().endswith(valid_extensions):
                name = os.path.splitext(filename)[0]
                full_path = os.path.join(asset_path, filename)
                try:
                    self.assets[name] = pygame.image.load(full_path).convert_alpha()
                except pygame.error as e:
                    print(f"無法載入圖片 {filename}: {e}")

    def get(self, name):
        return self.assets.get(name)

resource_manager = ResourceManager()

# ==========================================
# --- 全域狀態變數 ---
# ==========================================
score = 0
is_in_penalty_mode = False 
has_cleared_penalty = False 
penalty_timer = 0 
PENALTY_DURATION = 300 
is_dead = False 
death_timer = 0 

# 字體載入優化
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

# ==========================================
# --- 敵方單位與投射物 ---
# ==========================================

class Bullet(pygame.sprite.Sprite):
    """追蹤玩家位置的子彈"""
    def __init__(self, x, y, target_x, target_y):
        super().__init__()
        self.image = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(self.image, RED, (12, 12), 12)
        pygame.draw.circle(self.image, WHITE, (12, 12), 6)
        self.rect = self.image.get_rect(center=(x, y))
        
        # 計算移動角度
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

class AerialEnemy(pygame.sprite.Sprite):
    """空中飛行的敵人，會根據玩家分數解鎖並射擊"""
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

        # 移動邏輯
        self.rect.x += self.speed * self.direction
        if self.rect.right >= SCREEN_WIDTH:
            self.direction = -1
        elif self.rect.left <= 0:
            self.direction = 1

        # 射擊計時
        self.timer += 1
        if self.timer >= self.shoot_cooldown:
            self.timer = 0
            b = Bullet(self.rect.centerx, self.rect.centery, player_hitbox.centerx, player_hitbox.centery)
            bullet_group.add(b)
            all_group.add(b)

    def draw(self, surface):
        if self.active:
            surface.blit(self.image, self.rect)

# ==========================================
# ---陷阱與機關系統 ---
# ==========================================

class LaserCannon:
    """高功率雷射炮，具備警告期與發射期"""
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
        self.energy_particles = [] 

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
            
        # 警告粒子效果
        if self.is_warning:
            if len(self.energy_particles) < 20:
                px = self.x + random.randint(0, self.width)
                py = random.randint(50, 150)
                self.energy_particles.append({'x': px, 'y': py, 'life': 1.0})
            
            for p in self.energy_particles[:]:
                p['y'] -= 2 
                p['life'] -= 0.02
                if p['life'] <= 0: self.energy_particles.remove(p)

    def check_collision(self, target_hitbox, shield_active, shield_rect):
        if self.is_firing:
            laser_rect = pygame.Rect(self.x + 20, 0, self.width - 40, SCREEN_HEIGHT)
            if shield_active and laser_rect.colliderect(shield_rect):
                return False
            return laser_rect.colliderect(target_hitbox)
        return False

    def draw(self, surface):
        if not self.active: return
        
        # 砲台本體
        cannon_body = pygame.Rect(self.x, 0, self.width, 35)
        pygame.draw.rect(surface, (40, 40, 50), cannon_body, border_bottom_left_radius=10, border_bottom_right_radius=10)
        pygame.draw.rect(surface, GRAY, cannon_body, 2, border_bottom_left_radius=10, border_bottom_right_radius=10)
        
        # 警告狀態繪製
        if self.is_warning:
            warn_alpha = abs(math.sin(self.timer * 0.1)) * 60 + 20
            warn_surf = pygame.Surface((self.width, SCREEN_HEIGHT), pygame.SRCALPHA)
            pygame.draw.rect(warn_surf, (255, 0, 0, int(warn_alpha)), (0, 0, self.width, SCREEN_HEIGHT))
            surface.blit(warn_surf, (self.x, 0))
            for p in self.energy_particles:
                p_alpha = int(p['life'] * 255)
                pygame.draw.circle(surface, (255, 50, 50, p_alpha), (p['x'], p['y']), 3)

        # 發射狀態繪製 (華麗特效)
        if self.is_firing:
            main_beam_w = 40 + math.sin(self.timer * 0.5) * 10 
            main_beam_x = self.x + (self.width - main_beam_w) // 2
            pygame.draw.rect(surface, LASER_RED, (main_beam_x, 0, main_beam_w, SCREEN_HEIGHT))
            pygame.draw.rect(surface, WHITE, (main_beam_x + main_beam_w*0.3, 0, main_beam_w*0.4, SCREEN_HEIGHT))
            
    def reset_cycle(self):
        self.timer = random.randint(0, 100)
        self.is_firing = False
        self.is_warning = False
        self.energy_particles = []

class GroundSpikes:
    """地底伸出的尖刺，警告後快速穿刺"""
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
            self.is_warning, self.is_attacking, self.anim_frame = True, False, 0
        elif cycle_time == self.warning_duration:
            self.is_warning, self.is_attacking, self.anim_frame = False, True, 0
        elif cycle_time == self.warning_duration + self.attack_duration:
            self.is_attacking = False
        if self.is_attacking or self.is_warning: self.anim_frame += 1

    def check_collision(self, target_hitbox):
        if self.is_attacking:
            spike_rect = pygame.Rect(self.x, SCREEN_HEIGHT - self.height, self.width, self.height)
            return spike_rect.colliderect(target_hitbox)
        return False

    def draw(self, surface):
        if not self.active: return
        if self.is_warning:
            shake_x = random.randint(-2, 2)
            warn_alpha = abs(math.sin(self.anim_frame * 0.2)) * 150 + 50
            warn_surf = pygame.Surface((self.width, 15), pygame.SRCALPHA)
            pygame.draw.rect(warn_surf, (255, 0, 0, int(warn_alpha)), (0, 0, self.width, 15))
            surface.blit(warn_surf, (self.x + shake_x, SCREEN_HEIGHT - 15))
        if self.is_attacking:
            rise_ratio = min(1.0, self.anim_frame / 6.0)
            current_h = self.height * rise_ratio
            num_spikes = 6
            spike_w = self.width // num_spikes
            for i in range(num_spikes):
                base_x = self.x + (i * spike_w)
                points_main = [(base_x + 5, SCREEN_HEIGHT), (base_x + spike_w // 2, SCREEN_HEIGHT - current_h), (base_x + spike_w - 5, SCREEN_HEIGHT)]
                pygame.draw.polygon(surface, SPIKE_COLOR, points_main)

    def reset_cycle(self):
        self.timer = 0
        self.is_attacking, self.is_warning, self.anim_frame = False, False, 0

# ==========================================
# --- 商店與介面系統 ---
# ==========================================

class CharacterSelector:
    """開局時的英雄選擇介面"""
    def __init__(self):
        self.selected_base = "player"
        self.options = ["player", "player2"] 
        self.is_active = True
        self.option_rects = [pygame.Rect(150 + i * 300, 250, 200, 200) for i in range(len(self.options))]

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
                surface.blit(pygame.transform.scale(char_img, (180, 180)), (rect.x + 10, rect.y + 10))
        self.start_btn = pygame.Rect(300, 500, 200, 60)
        pygame.draw.rect(surface, BLUE, self.start_btn, border_radius=10)
        txt = font.render("START", True, WHITE)
        surface.blit(txt, (self.start_btn.centerx - txt.get_width()//2, self.start_btn.centery - txt.get_height()//2))

    def handle_click(self, pos):
        for i, rect in enumerate(self.option_rects):
            if rect.collidepoint(pos): self.selected_base = self.options[i]
        if self.start_btn.collidepoint(pos): self.is_active = False

class Shop:
    """遊戲中商店，提供多樣化能力升級"""
    def __init__(self):
        self.is_open = False
        self.items = [
            {"name": "提升速度 (Speed Up)", "cost": 500, "type": "speed"},
            {"name": "強力跳躍 (High Jump)", "cost": 800, "type": "jump"},
            {"name": "終極護盾 (Shield x1) [X]", "cost": 1000, "type": "shield"},
            {"name": "格擋系統 (BLOCK) [F]", "cost": 1200, "type": "block_skill"},
            {"name": "閃現 (Flash Step) [B]", "cost": 3567, "type": "flash_step"} 
        ]
        self.rect = pygame.Rect(150, 50, 500, 500) 
        self.close_button = pygame.Rect(600, 60, 40, 40)
        self.shield_count = 0
        self.has_block_skill = False
        self.has_flash_step = False

    def draw(self, surface):
        if not self.is_open: return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        pygame.draw.rect(surface, BLUE, self.rect, border_radius=15)
        title = font.render("Item Shop", True, GOLD)
        surface.blit(title, (self.rect.centerx - title.get_width()//2, self.rect.y + 20))
        
        for i, item in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x + 50, self.rect.y + 80 + (i * 80), 400, 70)
            pygame.draw.rect(surface, GRAY, item_rect, border_radius=10)
            surface.blit(shop_font.render(item['name'], True, WHITE), (item_rect.x+20, item_rect.y+10))
            surface.blit(shop_font.render(f"Cost: {item['cost']}", True, YELLOW), (item_rect.x+20, item_rect.y+40))

    def handle_click(self, pos, current_player):
        global score
        if not self.is_open: return False
        if self.close_button.collidepoint(pos): self.is_open = False; return True
        for i, item in enumerate(self.items):
            item_rect = pygame.Rect(self.rect.x + 50, self.rect.y + 80 + (i * 80), 400, 70)
            if item_rect.collidepoint(pos) and score >= item['cost']:
                score -= item['cost']
                self.apply_item(item['type'], current_player)
                return True
        return False

    def apply_item(self, item_type, current_player):
        if item_type == "speed": current_player.speed += 2
        elif item_type == "jump": current_player.jump_strength -= 3
        elif item_type == "shield": self.shield_count += 1
        elif item_type == "block_skill": self.has_block_skill = True
        elif item_type == "flash_step": self.has_flash_step = True

    def reset(self):
        self.shield_count, self.has_block_skill, self.has_flash_step = 0, False, False

# ==========================================
# --- 玩家類別 (核心邏輯) ---
# ==========================================

class Player(pygame.sprite.Sprite):
    def __init__(self, base_character):
        super().__init__()
        self.base_name = base_character 
        self.speed, self.jump_strength, self.velocity_y, self.gravity = PLAYER_SPEED, JUMP_STRENGTH, 0, GRAVITY
        self.is_jumping, self.level, self.shield_active, self.shield_timer = False, 1, False, 0
        self.shield_duration, self.shield_width, self.shield_height = 300, 500, 40
        self.shield_rect = pygame.Rect(0, 0, self.shield_width, self.shield_height)
        self.is_blocking, self.current_size = False, 200
        
        # 閃現相關 (30秒 CD = 1800 幀)
        self.flash_cd = 1800 
        self.flash_timer = 0
        
        self.load_player_images()
        self.image = self.idle_img
        self.rect = self.image.get_rect()
        self.rect.centerx, self.rect.bottom = SCREEN_WIDTH // 2, SCREEN_HEIGHT - 10
        self.ground_y = self.rect.bottom
        self.hit_rect = self.rect.inflate(-self.rect.width * 0.75, -self.rect.height * 0.4)

    def load_player_images(self):
        global is_in_penalty_mode
        idle_name = self.base_name + ('2' if is_in_penalty_mode or self.level >= 2 else '')
        jump_name = idle_name + '_jump'
        idle_res = resource_manager.get(idle_name) or resource_manager.get(self.base_name)
        self.idle_img = pygame.transform.scale(idle_res, (self.current_size, self.current_size)) if idle_res else pygame.Surface([self.current_size, self.current_size])
        jump_res = resource_manager.get(jump_name) or self.idle_img
        self.jump_img = pygame.transform.scale(jump_res, (self.current_size, self.current_size)) if jump_res else self.idle_img

    def check_evolution(self, current_score):
        global is_in_penalty_mode, penalty_timer, is_dead, has_cleared_penalty
        if current_score < 0 and not is_dead: self.trigger_death()
        # 進入懲罰模式判定
        if current_score >= 1500 and not is_in_penalty_mode and not has_cleared_penalty:
            is_in_penalty_mode, penalty_timer = True, PENALTY_DURATION
            self.load_player_images()
        if is_in_penalty_mode:
            penalty_timer -= 1
            if penalty_timer <= 0:
                is_in_penalty_mode, has_cleared_penalty, self.level = False, True, 1
                self.load_player_images()

    def trigger_death(self):
        global is_dead, death_timer
        if not is_dead: is_dead, death_timer = True, 120

    def jump(self):
        if not self.is_jumping and not self.is_blocking:
            self.velocity_y, self.is_jumping, self.image = self.jump_strength, True, self.jump_img

    def activate_shield(self):
        if shop.shield_count > 0 and not self.shield_active:
            shop.shield_count -= 1
            self.shield_active, self.shield_timer = True, self.shield_duration

    def use_flash_step(self):
        """瞬移到滑鼠位置"""
        if shop.has_flash_step and self.flash_timer <= 0:
            self.rect.center = pygame.mouse.get_pos()
            if self.rect.bottom > self.ground_y: self.rect.bottom = self.ground_y
            self.flash_timer = self.flash_cd

    def update(self):
        keys = pygame.key.get_pressed()
        self.is_blocking = keys[pygame.K_f] and shop.has_block_skill
        move_speed = 2 if self.is_blocking else self.speed
        if keys[pygame.K_LEFT]: self.rect.x -= move_speed
        if keys[pygame.K_RIGHT]: self.rect.x += move_speed
        
        if self.flash_timer > 0: self.flash_timer -= 1
            
        self.velocity_y += self.gravity
        self.rect.y += self.velocity_y
        if self.rect.bottom >= self.ground_y:
            self.rect.bottom, self.velocity_y = self.ground_y, 0
            if self.is_jumping: self.is_jumping, self.image = False, self.idle_img
        
        if self.shield_active:
            self.shield_rect.centerx, self.shield_rect.bottom = self.rect.centerx, self.rect.top - 10
            self.shield_timer -= 1
            if self.shield_timer <= 0: self.shield_active = False
        
        self.hit_rect.center = self.rect.center

    def draw_shield(self, surface):
        if self.shield_active:
            s = pygame.Surface((self.shield_width, self.shield_height), pygame.SRCALPHA)
            pygame.draw.rect(s, SHIELD_COLOR, (0, 0, self.shield_width, self.shield_height), border_radius=15)
            surface.blit(s, self.shield_rect.topleft)

# ==========================================
# --- 金幣類別 ---
# ==========================================

class Coin(pygame.sprite.Sprite):
    def __init__(self, current_score):
        super().__init__()
        self.type = "penalty" if is_in_penalty_mode else "normal"
        size = 180 if self.type == "penalty" else 70
        asset = 'flag3' if self.type == "penalty" else 'flag'
        img = resource_manager.get(asset)
        self.image = pygame.transform.scale(img, (size, size)) if img else pygame.Surface([size, size])
        self.rect = self.image.get_rect(x=random.randrange(0, SCREEN_WIDTH-size), y=-size)
        self.hit_rect = pygame.Rect(0, 0, size*0.8, size*0.8)

    def update(self):
        self.rect.y += COIN_SPEED
        self.hit_rect.center = self.rect.center

# ==========================================
# --- 主遊戲實例與控制迴圈 ---
# ==========================================

shop = Shop()
selector = CharacterSelector()
laser_cannons = [LaserCannon(2000), LaserCannon(4000), LaserCannon(6000)]
ground_spikes = GroundSpikes()
aerial_enemy = AerialEnemy()
bullets = pygame.sprite.Group()
all_sprites = pygame.sprite.Group() 
coins = pygame.sprite.Group()
player = None

def spawn_coin():
    c = Coin(score)
    all_sprites.add(c); coins.add(c)

def reset_game():
    global score, is_in_penalty_mode, has_cleared_penalty, is_dead, player
    score, is_in_penalty_mode, has_cleared_penalty, is_dead = 0, False, False, False
    for lc in laser_cannons: lc.reset_cycle()
    ground_spikes.reset_cycle(); all_sprites.empty(); bullets.empty()
    player = Player(selector.selected_base); all_sprites.add(player); shop.reset()

running, coin_counter = True, 0
while running:
    # 角色選擇階段
    if selector.is_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.MOUSEBUTTONDOWN: selector.handle_click(event.pos)
        selector.draw(screen)
        if not selector.is_active: reset_game()

    # 正式遊戲階段
    else:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if not is_dead:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE: player.jump()
                    if event.key == pygame.K_x: player.activate_shield()
                    if event.key == pygame.K_b: player.use_flash_step() 
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if pygame.Rect(10, 10, 260, 140).collidepoint(event.pos): shop.is_open = not shop.is_open
                    else: shop.handle_click(event.pos, player)

        if not shop.is_open and not is_dead:
            player.check_evolution(score)
            # 機關更新
            for lc in laser_cannons:
                lc.update(score)
                if lc.check_collision(player.hit_rect, player.shield_active, player.shield_rect): player.trigger_death()
            ground_spikes.update(score)
            if ground_spikes.check_collision(player.hit_rect): player.trigger_death()
            aerial_enemy.update(player.hit_rect, score, bullets, all_sprites)
            
            # 碰撞與得分
            for b in bullets:
                if player.hit_rect.colliderect(b.rect) and not player.is_blocking: player.trigger_death()
            
            all_sprites.update()
            coin_counter += 1
            if coin_counter % (PENALTY_COIN_FREQUENCY if is_in_penalty_mode else NORMAL_COIN_FREQUENCY) == 0: spawn_coin()
            
            for coin in list(coins):
                if player.hit_rect.colliderect(coin.hit_rect):
                    score += -100 if coin.type == "penalty" else 100
                    coin.kill()
                elif coin.rect.top > SCREEN_HEIGHT:
                    if coin.type == "normal": score -= 5
                    coin.kill()

        if is_dead:
            death_timer -= 1
            if death_timer <= 0: reset_game()

        # 繪圖順序
        screen.fill(BLACK)
        all_sprites.draw(screen)
        aerial_enemy.draw(screen)
        if player: player.draw_shield(screen)
        for lc in laser_cannons: lc.draw(screen)
        ground_spikes.draw(screen)
        
        # UI 繪製
        pygame.draw.rect(screen, DARK_GRAY, (10, 10, 260, 140), border_radius=10)
        screen.blit(font.render(f"Credits: {score}", True, WHITE), (20, 15))
        if is_in_penalty_mode: screen.blit(shop_font.render(f"DANGER: {penalty_timer//60+1}s", True, RED), (20, 50))
        
        # 技能 CD 與 狀態顯示
        if shop.has_flash_step:
            f_cd = player.flash_timer // 60
            color = RED if f_cd > 0 else YELLOW
            msg = f"Flash CD: {f_cd}s" if f_cd > 0 else "Flash READY (B)"
            screen.blit(shop_font.render(msg, True, color), (20, 75))
            screen.blit(shop_font.render(f"Shields: {shop.shield_count} (X)", True, BLUE), (20, 100))
        else:
            screen.blit(shop_font.render(f"Shields: {shop.shield_count} (X)", True, BLUE), (20, 75))
        screen.blit(shop_font.render("(Click UI to Shop)", True, GOLD), (20, 122))

        # 死亡畫面
        if is_dead:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((150, 0, 0, 180))
            screen.blit(overlay, (0, 0))
            m1 = big_font.render("GAME OVER", True, WHITE)
            m2 = font.render("You are such a failure", True, YELLOW)
            screen.blit(m1, (SCREEN_WIDTH//2 - m1.get_width()//2, SCREEN_HEIGHT//2 - 50))
            screen.blit(m2, (SCREEN_WIDTH//2 - m2.get_width()//2, SCREEN_HEIGHT//2 + 40))
        
        shop.draw(screen)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()