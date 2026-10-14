-- Configuración de CITrainer (Carnal Instinct, UE5 + UE4SS)
--
-- El trainer busca las variables del personaje por NOMBRE. Por defecto usa
-- patrones genéricos (subcadenas, en minúsculas). Si algo no funciona, pulsa
-- F7 en el juego, abre dump.txt (en la carpeta del mod), busca el nombre real
-- de la variable y ponlo en la lista "Exact" de su categoría: cuando "Exact"
-- tiene algo, sólo se usan esos nombres exactos y se ignoran los patrones.

return {
    Keys = {
        GodMode       = "F1",  -- vida infinita (on/off)
        AddMoney      = "F2",  -- + dinero
        InfStamina    = "F3",  -- stamina/energía infinita (on/off)
        AddStats      = "F4",  -- + atributos del personaje
        AddXP         = "F5",  -- + experiencia y puntos de habilidad
        UnlockAll     = "F6",  -- desbloquear todo + dar todos los objetos
        Dump          = "F7",  -- volcar variables/funciones/objetos a dump.txt
        ItemTracker   = "F8",  -- rastreador de objetos (on/off)
        SuperSpeed    = "F9",  -- velocidad x2 (on/off)
    },

    MoneyAmount  = 10000,
    StatStep     = 10,
    XPAmount     = 5000,
    PointsAmount = 10,
    SpeedMultiplier = 2.0,

    -- Categorías de variables. Patterns = subcadenas (minúsculas).
    Health = {
        Patterns = { "health", "hitpoint", "vida", "life" },
        Exact = {},
    },
    Stamina = {
        Patterns = { "stamina", "energy", "mana", "endurance" },
        Exact = {},
    },
    Money = {
        Patterns = { "money", "gold", "coin", "cash", "currency", "credit", "dinero", "wallet" },
        Exact = {},
    },
    Stats = {
        Patterns = { "strength", "agility", "dexterity", "intelligence", "charisma",
                     "vitality", "constitution", "luck", "wisdom", "attack", "defense",
                     "armor", "power", "speed", "skill" },
        Exact = {},
    },
    XP = {
        Patterns = { "experience", "xp" },
        Exact = {},
    },
    Points = {
        Patterns = { "skillpoint", "attributepoint", "perkpoint", "statpoint", "upgradepoint" },
        Exact = {},
    },
    -- Booleans que se ponen a true con F6 (galería, escenas, logros, objetos...).
    Unlock = {
        Patterns = { "unlocked", "collected", "discovered", "owned", "purchased",
                     "acquired", "obtained", "seen", "completed" },
        Exact = {},
    },
    -- Arrays/mapas que el rastreador vigila para detectar objetos nuevos.
    Inventory = {
        Patterns = { "inventory", "item", "collect", "unlock", "loot", "equipment", "gallery" },
        Exact = {},
    },

    -- Palabras que descartan una variable (para no tocar "MaxHealth",
    -- "HealthRegenRate", etc. cuando se busca la vida actual).
    IgnoreWords = { "max", "regen", "rate", "delay", "cooldown", "percent", "ratio",
                    "multiplier", "mult", "threshold", "damage", "cost", "drain",
                    "widget", "bar", "color", "colour", "scale", "time", "duration" },

    -- Patrones para el catálogo de objetos del juego (assets en /Game/).
    ItemAssetPatterns = { "item", "pickup", "collectible", "loot", "weapon", "outfit",
                          "costume", "consumable", "potion", "key" },

    -- Assets a cargar antes de "dar todo" (sólo se ven los assets cargados).
    -- Ejemplo: "/Game/Data/Items/DA_Sword.DA_Sword"
    PreloadAssets = {},

    -- Función para dar objetos. Con Auto = true el trainer busca sola una
    -- función tipo AddItem/GiveItem en el jugador, sus componentes y el
    -- GameInstance, y la llama con cada objeto compatible.
    -- Si no acierta, mira la sección FUNCIONES de dump.txt y rellena:
    --   Object   = nombre (o parte) de la clase que tiene la función, p.ej. "InventoryComponent"
    --   Function = nombre exacto, p.ej. "AddItem"
    -- Desactivado por defecto: llamar a una función equivocada puede cerrar
    -- el juego. Actívalo (true) sólo cuando dump.txt muestre la función buena.
    GiveAll = {
        Auto = false,
        Object = "",
        Function = "",
        Quantity = 1,
    },

    -- Hooks opcionales para registrar recogidas de objetos. Ruta completa de
    -- la función (sale en dump.txt), p.ej.
    -- "/Game/Blueprints/BP_Pickup.BP_Pickup_C:OnPickedUp"
    ItemPickupHooks = {},

    TrackIntervalMs  = 2000,
    GodTickMs        = 100,
}
