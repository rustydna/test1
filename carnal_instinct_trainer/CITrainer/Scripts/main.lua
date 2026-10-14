-- CITrainer: trainer genérico para Carnal Instinct (Unreal Engine 5) sobre UE4SS.
-- Ver README.md para instalación y uso.

local UEHelpers = require("UEHelpers")
local Config = require("config")

local TAG = "[CITrainer] "
local function log(msg) print(TAG .. tostring(msg) .. "\n") end

-- Carpeta del mod (para escribir dump.txt / items_seen.log junto a él).
local ModDir = (function()
    local src = debug.getinfo(1, "S").source or ""
    src = src:gsub("^@", ""):gsub("\\", "/")
    local dir = src:match("^(.*)/Scripts/[^/]*$")
    return dir and (dir .. "/") or ""
end)()

------------------------------------------------------------------------
-- Utilidades
------------------------------------------------------------------------

local function safe(fn, ...)
    local ok, res = pcall(fn, ...)
    if ok then return res end
    return nil
end

local function valid(o)
    if o == nil then return false end
    return safe(function() return o:IsValid() end) == true
end

local function fname(o) return safe(function() return o:GetFName():ToString() end) or "?" end
local function fullname(o) return safe(function() return o:GetFullName() end) or "?" end
local function addr(o) return safe(function() return o:GetAddress() end) end
local function className(o) return safe(function() return o:GetClass():GetFName():ToString() end) or "?" end

local function isCDO(o) return fname(o):find("^Default__") ~= nil end

local function lower(s) return string.lower(s or "") end

local function containsAny(s, list)
    for _, p in ipairs(list or {}) do
        if s:find(p, 1, true) then return p end
    end
    return nil
end

local function writeFile(name, text, append)
    local f = io.open(ModDir .. name, append and "a" or "w")
    if not f then log("No se pudo escribir " .. ModDir .. name); return false end
    f:write(text)
    f:close()
    return true
end

-- Clases del motor: sus propiedades no se tocan ni se vuelcan.
local ENGINE_PKG = { "/Script/Engine.", "/Script/CoreUObject.", "/Script/UMG.",
    "/Script/GameplayAbilities.", "/Script/AIModule.", "/Script/EnhancedInput.",
    "/Script/Niagara.", "/Script/ModularGameplay.", "/Script/CommonUI.",
    "/Script/SlateCore.", "/Script/Slate.", "/Script/PhysicsCore.",
    "/Script/GameplayTags.", "/Script/NavigationSystem.", "/Script/MovieScene.",
    "/Script/LevelSequence.", "/Script/Chaos." }

local function isEngineClass(cls)
    local fn = fullname(cls)
    for _, p in ipairs(ENGINE_PKG) do
        if fn:find(p, 1, true) then return true end
    end
    return false
end

-- Recorre las propiedades propias del juego (no del motor) de un objeto.
local function forEachGameProp(obj, cb)
    local cls = safe(function() return obj:GetClass() end)
    local seen = {}
    while valid(cls) and not isEngineClass(cls) do
        safe(function()
            cls:ForEachProperty(function(p)
                local n = p:GetFName():ToString()
                if not seen[n] then
                    seen[n] = true
                    cb(p, n, p:GetClass():GetFName():ToString())
                end
            end)
        end)
        cls = safe(function() return cls:GetSuperStruct() end)
    end
end

-- Tipo de struct de una StructProperty (p.ej. "GameplayAttributeData").
local function structName(p)
    return safe(function() return p:GetStruct():GetFName():ToString() end) or ""
end

local function isAttrProp(p) return structName(p) == "GameplayAttributeData" end

-- Propiedad interna de un ArrayProperty.
local function innerProp(p)
    return safe(function() return p:GetInner() end)
end

local function propType(p)
    return safe(function() return p:GetClass():GetFName():ToString() end) or "?"
end

local function forEachGameFunc(obj, cb)
    local cls = safe(function() return obj:GetClass() end)
    while valid(cls) and not isEngineClass(cls) do
        safe(function()
            cls:ForEachFunction(function(f) cb(f, f:GetFName():ToString(), cls) end)
        end)
        cls = safe(function() return cls:GetSuperStruct() end)
    end
end

local function funcParams(f)
    local params = {}
    safe(function()
        f:ForEachProperty(function(p)
            table.insert(params, { name = p:GetFName():ToString(), type = p:GetClass():GetFName():ToString(), prop = p })
        end)
    end)
    return params
end

------------------------------------------------------------------------
-- Lectura/escritura de números (int, float, double y GameplayAttributeData)
------------------------------------------------------------------------

local NUMERIC = { FloatProperty = true, DoubleProperty = true, IntProperty = true,
                  Int64Property = true, UInt32Property = true, Int16Property = true }
local INTEGER = { IntProperty = true, Int64Property = true, UInt32Property = true, Int16Property = true }

local function readNum(obj, name, ptype)
    if NUMERIC[ptype] then
        local v = safe(function() return obj[name] end)
        if type(v) == "number" then return v end
    elseif ptype == "StructProperty" then
        local s = safe(function() return obj[name] end)
        local v = s and safe(function() return s.CurrentValue end)
        if type(v) == "number" then return v end
    end
    return nil
end

local function writeNum(obj, name, ptype, val)
    if INTEGER[ptype] then
        val = math.floor(val + 0.5)
        if ptype ~= "Int64Property" and val > 2147483647 then val = 2147483647 end
    end
    if NUMERIC[ptype] then
        safe(function() obj[name] = val end)
    elseif ptype == "StructProperty" then
        local s = safe(function() return obj[name] end)
        if s then
            safe(function() s.BaseValue = val end)
            safe(function() s.CurrentValue = val end)
        end
    end
end

------------------------------------------------------------------------
-- Objetos del jugador
------------------------------------------------------------------------

local Cache = { time = 0, pawnAddr = nil, targets = {}, fields = {} }

local function getCore()
    local core = {}
    local pc = safe(function() return UEHelpers.GetPlayerController() end)
    if valid(pc) then
        core.pc = pc
        local pawn = safe(function() return pc.Pawn end)
        if valid(pawn) then core.pawn = pawn end
        local ps = safe(function() return pc.PlayerState end)
        if valid(ps) then core.ps = ps end
    end
    local gi = safe(function() return UEHelpers.GetGameInstance() end) or FindFirstOf("GameInstance")
    if valid(gi) then core.gi = gi end
    local gs = FindFirstOf("GameStateBase")
    if valid(gs) then core.gs = gs end
    return core
end

-- Jugador + controller + PlayerState + GameInstance + GameState y los
-- objetos a los que apuntan sus variables (componentes, AttributeSets,
-- inventarios, SaveGame...) hasta 2 niveles. No se recorre toda la memoria.
local ActorClass = nil
local function isActor(o)
    if not ActorClass then ActorClass = safe(function() return StaticFindObject("/Script/Engine.Actor") end) end
    if not valid(ActorClass) then return false end
    return safe(function() return o:IsA(ActorClass) end) == true
end

local function collectTargets()
    local core = getCore()
    local list, seen = {}, {}
    local queue = {}
    local function add(o, depth)
        local a = addr(o)
        if a and not seen[a] then
            seen[a] = true
            table.insert(list, o)
            table.insert(queue, { o, depth })
        end
    end
    for _, o in pairs(core) do add(o, 0) end
    local i = 1
    while i <= #queue do
        local obj, depth = queue[i][1], queue[i][2]
        i = i + 1
        if depth < 2 then
            forEachGameProp(obj, function(p, n, t)
                local candidates = {}
                if t == "ObjectProperty" then
                    table.insert(candidates, safe(function() return obj[n] end))
                elseif t == "ArrayProperty" and propType(innerProp(p)) == "ObjectProperty" then
                    safe(function()
                        local arr = obj[n]
                        local count = arr:GetArrayNum()
                        for k = 1, math.min(count, 32) do table.insert(candidates, arr[k]) end
                    end)
                end
                for _, v in ipairs(candidates) do
                    if valid(v) and not isCDO(v) and not isActor(v)
                       and not isEngineClass(safe(function() return v:GetClass() end)) then
                        add(v, depth + 1)
                    end
                end
            end)
        end
    end
    return core, list
end

local function buildFields(targets)
    local fields = {}
    for _, obj in ipairs(targets) do
        forEachGameProp(obj, function(p, n, t)
            table.insert(fields, { obj = obj, name = n, lname = lower(n), type = t, prop = p })
        end)
    end
    return fields
end

local function refresh(force)
    local now = os.clock()
    local core = getCore()
    local pawnAddr = core.pawn and addr(core.pawn)
    if force or pawnAddr ~= Cache.pawnAddr or (now - Cache.time) > 15 then
        local _, targets = collectTargets()
        Cache.core, Cache.targets = core, targets
        Cache.fields = buildFields(targets)
        Cache.pawnAddr, Cache.time = pawnAddr, now
    end
    return Cache
end

-- Campos de una categoría (Exact manda sobre Patterns).
local function matchCategory(cat, fieldTypeOk, opts)
    opts = opts or {}
    local res = {}
    local exact = {}
    for _, n in ipairs(cat.Exact or {}) do exact[lower(n)] = true end
    local useExact = next(exact) ~= nil
    for _, f in ipairs(Cache.fields) do
        if fieldTypeOk(f) and valid(f.obj) then
            local hit
            if useExact then
                hit = exact[f.lname] and f.lname
            else
                hit = containsAny(f.lname, cat.Patterns)
                if hit and not opts.allowIgnored and containsAny(f.lname, Config.IgnoreWords) then hit = nil end
            end
            if hit then f.hit = hit; table.insert(res, f) end
        end
    end
    return res
end

local function isNumericField(f)
    if NUMERIC[f.type] then return true end
    if f.type == "StructProperty" then return isAttrProp(f.prop) and readNum(f.obj, f.name, f.type) ~= nil end
    return false
end

local function describe(f) return className(f.obj) .. "." .. f.name end

------------------------------------------------------------------------
-- Vida / stamina infinitas
------------------------------------------------------------------------

-- Busca el "Max" correspondiente en el mismo objeto (Health -> MaxHealth).
local function findMaxField(f)
    local base = f.hit or ""
    local stripped = f.lname:gsub("^current", ""):gsub("^cur", "")
    for _, g in ipairs(Cache.fields) do
        if g.obj == f.obj or addr(g.obj) == addr(f.obj) then
            if g.lname ~= f.lname and g.lname:find("max", 1, true)
               and (g.lname:find(stripped, 1, true) or g.lname:find(base, 1, true))
               and isNumericField(g) then
                return g
            end
        end
    end
    return nil
end

local Lock = { god = false, stamina = false, godFields = nil, staFields = nil, peaks = {} }

local function prepareLock(cat)
    refresh(true)
    local fields = matchCategory(cat, isNumericField)
    for _, f in ipairs(fields) do
        f.max = findMaxField(f)
        f.peak = readNum(f.obj, f.name, f.type) or 0
    end
    return fields
end

local function tickLock(fields)
    for _, f in ipairs(fields or {}) do
        if valid(f.obj) then
            local cur = readNum(f.obj, f.name, f.type)
            if cur then
                local target = f.max and readNum(f.max.obj, f.max.name, f.max.type) or nil
                if not target or target <= 0 then
                    if cur > f.peak then f.peak = cur end
                    target = f.peak
                end
                if cur < target then writeNum(f.obj, f.name, f.type, target) end
            end
        end
    end
end

local function setPawnDamage(canBeDamaged)
    local core = getCore()
    if core.pawn then safe(function() core.pawn.bCanBeDamaged = canBeDamaged end) end
end

local function listFields(title, fields)
    if #fields == 0 then
        log(title .. ": no se encontró ninguna variable. Pulsa F7 y revisa dump.txt / config.lua.")
        return
    end
    for _, f in ipairs(fields) do
        log(title .. ": " .. describe(f) .. (f.max and ("  (max: " .. f.max.name .. ")") or ""))
    end
end

local function toggleGod()
    Lock.god = not Lock.god
    if Lock.god then
        Lock.godFields = prepareLock(Config.Health)
        setPawnDamage(false)
        listFields("Modo dios", Lock.godFields)
        log("Modo dios ACTIVADO")
    else
        setPawnDamage(true)
        log("Modo dios desactivado")
    end
end

local function toggleStamina()
    Lock.stamina = not Lock.stamina
    if Lock.stamina then
        Lock.staFields = prepareLock(Config.Stamina)
        listFields("Stamina", Lock.staFields)
        log("Stamina infinita ACTIVADA")
    else
        log("Stamina infinita desactivada")
    end
end

local lastPawnForLocks = nil
LoopAsync(Config.GodTickMs or 100, function()
    if Lock.god or Lock.stamina then
        ExecuteInGameThread(function()
            -- Si el jugador cambia (muerte, cambio de nivel) se re-buscan los campos.
            local core = getCore()
            local pa = core.pawn and addr(core.pawn)
            if pa ~= lastPawnForLocks then
                lastPawnForLocks = pa
                if Lock.god then Lock.godFields = prepareLock(Config.Health); setPawnDamage(false) end
                if Lock.stamina then Lock.staFields = prepareLock(Config.Stamina) end
            end
            if Lock.god then tickLock(Lock.godFields) end
            if Lock.stamina then tickLock(Lock.staFields) end
        end)
    end
    return false
end)

------------------------------------------------------------------------
-- Dinero, atributos, experiencia
------------------------------------------------------------------------

local function addToCategory(title, cat, amount)
    refresh(true)
    local fields = matchCategory(cat, isNumericField)
    if #fields == 0 then
        log(title .. ": no se encontró ninguna variable. Pulsa F7 y revisa dump.txt / config.lua.")
        return
    end
    for _, f in ipairs(fields) do
        local cur = readNum(f.obj, f.name, f.type) or 0
        writeNum(f.obj, f.name, f.type, cur + amount)
        log(string.format("%s: %s %s -> %s", title, describe(f), tostring(cur),
            tostring(readNum(f.obj, f.name, f.type))))
    end
end

local function addMoney() addToCategory("Dinero", Config.Money, Config.MoneyAmount) end
local function addStats() addToCategory("Atributos", Config.Stats, Config.StatStep) end
local function addXP()
    addToCategory("Experiencia", Config.XP, Config.XPAmount)
    addToCategory("Puntos", Config.Points, Config.PointsAmount)
end

------------------------------------------------------------------------
-- Velocidad
------------------------------------------------------------------------

local Speed = { on = false, walk = nil, jump = nil }

local function toggleSpeed()
    local core = getCore()
    local move = core.pawn and safe(function() return core.pawn.CharacterMovement end)
    if not valid(move) then log("No hay CharacterMovement en el jugador"); return end
    Speed.on = not Speed.on
    local m = Config.SpeedMultiplier or 2
    if Speed.on then
        Speed.walk = move.MaxWalkSpeed
        Speed.jump = move.JumpZVelocity
        move.MaxWalkSpeed = Speed.walk * m
        move.JumpZVelocity = Speed.jump * math.sqrt(m)
        log("Velocidad x" .. m .. " ACTIVADA")
    else
        if Speed.walk then move.MaxWalkSpeed = Speed.walk end
        if Speed.jump then move.JumpZVelocity = Speed.jump end
        log("Velocidad normal")
    end
end

------------------------------------------------------------------------
-- Catálogo de objetos del juego
------------------------------------------------------------------------

local function preloadAssets()
    for _, path in ipairs(Config.PreloadAssets or {}) do
        local o = safe(function() return StaticFindObject(path) end)
        if not valid(o) then
            safe(function() LoadAsset(path) end)
        end
    end
end

-- Assets (no instancias en el mundo) bajo /Game/ cuyo nombre o clase
-- coincide con ItemAssetPatterns.
local function buildItemCatalog()
    preloadAssets()
    local catalog = {}
    ForEachUObject(function(o)
        -- Una sola llamada por objeto: "Clase /Game/Ruta/Asset.Asset"
        local fn = fullname(o)
        if not fn:find(" /Game/", 1, true) then return end
        local cn, path = fn:match("^(%S+) (.*)$")
        if not cn then return end
        local n = lower(path:match("([^%.:/]+)$") or "")
        if n:find("^default__") or n:find("^skel_") or n:find("^reinst_") then return end
        local hit = containsAny(n, Config.ItemAssetPatterns) or containsAny(lower(cn), Config.ItemAssetPatterns)
        if not hit then return end
        local outer = safe(function() return o:GetOuter() end)
        local isAsset = outer and className(outer) == "Package"
        local kind = isAsset and (cn == "BlueprintGeneratedClass" and "clase" or (cn == "DataTable" and "tabla" or "asset")) or "en mundo"
        table.insert(catalog, { obj = o, kind = kind, full = fn })
    end)
    table.sort(catalog, function(a, b) return a.full < b.full end)
    return catalog
end

------------------------------------------------------------------------
-- Rastreador de objetos (detecta lo que se va consiguiendo)
------------------------------------------------------------------------

local Tracker = { on = false, known = {}, primed = false }

local SIMPLE = { IntProperty = true, Int64Property = true, FloatProperty = true, DoubleProperty = true,
                 BoolProperty = true, ByteProperty = true, NameProperty = true, StrProperty = true,
                 ObjectProperty = true, ClassProperty = true }

local function valueToString(v)
    if v == nil then return nil end
    if type(v) ~= "userdata" then return tostring(v) end
    if valid(v) then return fullname(v) end
    local s = safe(function() return v:ToString() end)
    if type(s) == "string" then return s end
    return nil
end

-- Lee las entradas de un array. Sólo tipos simples o structs con campos
-- simples (mapas, sets y otros tipos pueden tumbar el juego).
local function containerEntries(obj, name, p)
    local out = {}
    local inner = innerProp(p)
    local it = propType(inner)
    local fields
    if it == "StructProperty" then
        fields = {}
        safe(function()
            inner:GetStruct():ForEachProperty(function(q)
                local qt = q:GetClass():GetFName():ToString()
                if SIMPLE[qt] and #fields < 6 then table.insert(fields, q:GetFName():ToString()) end
            end)
        end)
        if #fields == 0 then return out end
    elseif not SIMPLE[it] then
        return out
    end
    safe(function()
        local arr = obj[name]
        local count = arr:GetArrayNum()
        for k = 1, math.min(count, 512) do
            local e = arr[k]
            if fields then
                local parts = {}
                for _, fn in ipairs(fields) do
                    local sv = valueToString(safe(function() return e[fn] end))
                    if sv then table.insert(parts, fn .. "=" .. sv) end
                end
                if #parts > 0 then table.insert(out, "{" .. table.concat(parts, ", ") .. "}") end
            else
                local sv = valueToString(e)
                if sv then table.insert(out, sv) end
            end
        end
    end)
    return out
end

local CONTAINER = { ArrayProperty = true }

local function trackerTick()
    refresh(false)
    local fields = matchCategory(Config.Inventory, function(f) return CONTAINER[f.type] end, { allowIgnored = true })
    local newLines = {}
    for _, f in ipairs(fields) do
        local key = className(f.obj) .. "." .. f.name
        for _, e in ipairs(containerEntries(f.obj, f.name, f.prop)) do
            local id = key .. " | " .. e
            if not Tracker.known[id] then
                Tracker.known[id] = true
                if Tracker.primed then table.insert(newLines, id) end
            end
        end
    end
    if not Tracker.primed then
        Tracker.primed = true
        local n = 0
        for _ in pairs(Tracker.known) do n = n + 1 end
        log("Rastreador: " .. n .. " entradas iniciales en " .. #fields .. " contenedores")
        return
    end
    if #newLines > 0 then
        local stamp = os.date("%Y-%m-%d %H:%M:%S")
        local buf = {}
        for _, l in ipairs(newLines) do
            log("NUEVO OBJETO: " .. l)
            table.insert(buf, stamp .. "  " .. l .. "\n")
        end
        writeFile("items_seen.log", table.concat(buf), true)
    end
end

LoopAsync(Config.TrackIntervalMs or 2000, function()
    if Tracker.on then ExecuteInGameThread(function() safe(trackerTick) end) end
    return false
end)

local function toggleTracker()
    Tracker.on = not Tracker.on
    log("Rastreador de objetos " .. (Tracker.on and "ACTIVADO (items_seen.log)" or "desactivado"))
end

for _, path in ipairs(Config.ItemPickupHooks or {}) do
    local ok, err = pcall(function()
        RegisterHook(path, function(self, ...)
            local line = os.date("%Y-%m-%d %H:%M:%S") .. "  HOOK " .. path .. " | " .. fullname(self:get())
            local args = { ... }
            for i, a in ipairs(args) do
                line = line .. " | arg" .. i .. "=" .. (valueToString(safe(function() return a:get() end)) or "?")
            end
            log(line)
            writeFile("items_seen.log", line .. "\n", true)
        end)
    end)
    if not ok then log("No se pudo enganchar " .. path .. ": " .. tostring(err)) end
end

------------------------------------------------------------------------
-- Desbloquear todo / dar todos los objetos
------------------------------------------------------------------------

local function unlockBools()
    refresh(true)
    local fields = matchCategory(Config.Unlock, function(f) return f.type == "BoolProperty" end, { allowIgnored = true })
    local n = 0
    for _, f in ipairs(fields) do
        if safe(function() return f.obj[f.name] end) == false then
            safe(function() f.obj[f.name] = true end)
            n = n + 1
            log("Desbloqueado: " .. describe(f))
        end
    end
    -- Arrays de bool (p.ej. GalleryUnlocked[])
    local arrays = matchCategory(Config.Unlock, function(f) return f.type == "ArrayProperty" end, { allowIgnored = true })
    for _, f in ipairs(arrays) do
        if propType(innerProp(f.prop)) == "BoolProperty" then
            safe(function()
                local arr = f.obj[f.name]
                for k = 1, arr:GetArrayNum() do
                    if arr[k] == false then arr[k] = true; n = n + 1 end
                end
            end)
        end
    end
    log("Desbloqueos booleanos: " .. n)
end

local function isChildOf(cls, base)
    local ba = addr(base)
    local c = cls
    while valid(c) do
        if addr(c) == ba then return true end
        c = safe(function() return c:GetSuperStruct() end)
    end
    return false
end

-- Busca una función para dar objetos en los objetos del jugador.
local function findGiveFunctions()
    local found = {}
    local wantObj, wantFn = lower(Config.GiveAll.Object or ""), Config.GiveAll.Function or ""
    for _, obj in ipairs(Cache.targets) do
        forEachGameFunc(obj, function(f, n, cls)
            local ok
            if wantFn ~= "" then
                ok = n == wantFn and (wantObj == "" or lower(className(obj)):find(wantObj, 1, true))
            else
                local ln = lower(n)
                ok = (ln:find("^add") or ln:find("^give") or ln:find("^grant") or ln:find("^receive") or ln:find("^pickup"))
                     and (ln:find("item") or ln:find("inventory") or ln:find("collect") or ln:find("loot"))
            end
            if ok then table.insert(found, { obj = obj, fn = f, name = n, params = funcParams(f) }) end
        end)
    end
    return found
end

-- Decide cómo llamar a la función: (objeto), (objeto, cantidad), (clase, cantidad)...
local function planCall(cand)
    local p = cand.params
    local inputs = {}
    for _, q in ipairs(p) do
        local ln = lower(q.name)
        if ln ~= "returnvalue" and not ln:find("^out") and not ln:find("success") and not ln:find("result") then
            table.insert(inputs, q)
        end
    end
    if #inputs == 0 or #inputs > 3 then return nil end
    local first = inputs[1]
    local plan = { kind = first.type, extras = {} }
    if first.type == "ObjectProperty" then
        plan.base = safe(function() return first.prop:GetPropertyClass() end)
    elseif first.type == "ClassProperty" then
        plan.base = safe(function() return first.prop:GetMetaClass() end)
    else
        return nil
    end
    if not valid(plan.base) then return nil end
    for i = 2, #inputs do
        local t = inputs[i].type
        if INTEGER[t] or t == "FloatProperty" or t == "DoubleProperty" then
            table.insert(plan.extras, Config.GiveAll.Quantity or 1)
        elseif t == "BoolProperty" then
            table.insert(plan.extras, false)
        else
            return nil
        end
    end
    return plan
end

local function giveAllItems()
    refresh(true)
    local cands = findGiveFunctions()
    if #cands == 0 then
        log("Dar objetos: no se encontró ninguna función AddItem/GiveItem. Pulsa F7 y configura GiveAll en config.lua.")
        return
    end
    preloadAssets()
    for _, cand in ipairs(cands) do
        local plan = planCall(cand)
        local sig = {}
        for _, q in ipairs(cand.params) do table.insert(sig, q.type .. " " .. q.name) end
        log("Función candidata: " .. className(cand.obj) .. ":" .. cand.name .. "(" .. table.concat(sig, ", ") .. ")")
        if plan and (Config.GiveAll.Auto or Config.GiveAll.Function ~= "") then
            local items = {}
            ForEachUObject(function(o)
                if isCDO(o) then return end
                local fn = fullname(o)
                if not fn:find(" /Game/", 1, true) then return end
                if plan.kind == "ObjectProperty" then
                    local outer = safe(function() return o:GetOuter() end)
                    if outer and className(outer) == "Package" and safe(function() return o:IsA(plan.base) end) then
                        table.insert(items, o)
                    end
                elseif className(o) == "BlueprintGeneratedClass" then
                    local n = lower(fname(o))
                    if not n:find("^skel_") and not n:find("^reinst_") and isChildOf(o, plan.base) then
                        table.insert(items, o)
                    end
                end
            end)
            local okCount = 0
            for _, item in ipairs(items) do
                local ok = pcall(function() cand.obj[cand.name](cand.obj, item, table.unpack(plan.extras)) end)
                if ok then okCount = okCount + 1 end
            end
            log(string.format("Dados %d/%d objetos de tipo %s con %s", okCount, #items, fname(plan.base), cand.name))
            if okCount > 0 then return end
        elseif not plan then
            log("  (firma no reconocida; configúrala a mano o usa otra función)")
        end
    end
end

local function unlockAll()
    unlockBools()
    giveAllItems()
end

------------------------------------------------------------------------
-- Volcado (F7)
------------------------------------------------------------------------

local function simpleValue(obj, name, t, p)
    if NUMERIC[t] or t == "BoolProperty" or t == "StrProperty" or t == "NameProperty" or t == "TextProperty" then
        local v = safe(function() return obj[name] end)
        if type(v) == "userdata" then v = safe(function() return v:ToString() end) end
        return tostring(v)
    elseif t == "StructProperty" and isAttrProp(p) then
        local v = readNum(obj, name, t)
        if v then return "Attr " .. tostring(v) end
    elseif t == "ObjectProperty" then
        local v = safe(function() return obj[name] end)
        if valid(v) then return fullname(v) end
    elseif CONTAINER[t] then
        local e = containerEntries(obj, name, p)
        local s = #e .. " elem"
        if #e > 0 then s = s .. ": " .. table.concat(e, " ; ", 1, math.min(#e, 10)) end
        return s
    end
    return ""
end

local function dump()
    local c = refresh(true)
    local out = {}
    local function w(s) table.insert(out, s) end
    w("CITrainer dump " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
    w("Usa los nombres de VARIABLE de abajo en las listas Exact de config.lua.\n\n")
    w("== OBJETOS DEL JUGADOR ==\n")
    for k, o in pairs(c.core or {}) do w(string.format("  %-5s %s\n", k, fullname(o))) end
    w("\n== VARIABLES (clase.variable [tipo] = valor) ==\n")
    for _, obj in ipairs(c.targets) do
        local lines = {}
        forEachGameProp(obj, function(p, n, t)
            table.insert(lines, string.format("    %s [%s] = %s\n", n, t, simpleValue(obj, n, t, p) or ""))
        end)
        if #lines > 0 then
            w("\n  " .. fullname(obj) .. "\n")
            for _, l in ipairs(lines) do w(l) end
        end
    end
    w("\n== FUNCIONES ==\n")
    for _, obj in ipairs(c.targets) do
        forEachGameFunc(obj, function(f, n, cls)
            local sig = {}
            for _, q in ipairs(funcParams(f)) do table.insert(sig, q.type .. " " .. q.name) end
            w(string.format("  %s:%s(%s)\n", (fullname(cls):gsub("^%S+ ", "")), n, table.concat(sig, ", ")))
        end)
    end
    w("\n== CATÁLOGO DE OBJETOS CARGADOS ==\n")
    local catalog = buildItemCatalog()
    for _, it in ipairs(catalog) do w(string.format("  [%-8s] %s\n", it.kind, it.full)) end
    w(string.format("\nTotal: %d objetos/variables del jugador, %d entradas de catálogo\n", #c.targets, #catalog))
    writeFile("dump.txt", table.concat(out))
    writeFile("items_catalog.txt", (function()
        local b = {}
        for _, it in ipairs(catalog) do table.insert(b, it.kind .. "\t" .. it.full .. "\n") end
        return table.concat(b)
    end)())
    log("Volcado escrito en " .. ModDir .. "dump.txt y items_catalog.txt (" .. #catalog .. " objetos en catálogo)")
end

------------------------------------------------------------------------
-- Teclas
------------------------------------------------------------------------

local Actions = {
    GodMode = toggleGod,
    AddMoney = addMoney,
    InfStamina = toggleStamina,
    AddStats = addStats,
    AddXP = addXP,
    UnlockAll = unlockAll,
    Dump = dump,
    ItemTracker = toggleTracker,
    SuperSpeed = toggleSpeed,
}

for action, keyName in pairs(Config.Keys) do
    local key = Key[keyName]
    local fn = Actions[action]
    if key and fn then
        RegisterKeyBind(key, function()
            ExecuteInGameThread(function()
                local ok, err = pcall(fn)
                if not ok then log(action .. " falló: " .. tostring(err)) end
            end)
        end)
    else
        log("Tecla no válida para " .. action .. ": " .. tostring(keyName))
    end
end

log("Cargado. F1 dios | F2 dinero | F3 stamina | F4 atributos | F5 XP | F6 desbloquear todo | F7 volcado | F8 rastreador | F9 velocidad")
