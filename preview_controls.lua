-- Preview Control Script for MAME
-- This script launches the preview window on a second screen when a game is paused
-- Compatible with multiple MAME versions

local exports = {}
exports.name = "preview_control"
exports.version = "0.1"
exports.description = "Show control preview on second screen when game is paused"
exports.license = "MIT"
exports.author = { name = "Claude" }

-- Configuration
local config = {
    preview_app_path = "F:/Deluxe Universe/emulators/mame/MAME Controls - New.py", -- Update with your actual path
    python_exe = "python", -- Python executable path
    screen = 2,            -- Screen number to display preview on
    auto_close = true      -- Automatically close preview when MAME exits or unpauses
}

-- Debug function
local function debug_print(msg)
    print("[PREVIEW CONTROL] " .. msg)
end

-- Find the executable path (updates config.preview_app_path)
local function find_preview_app_path()
    local paths_to_check = {
        emu.subst_env("${MAMEPATH}\\MAMEControlConfig.py"),
        emu.subst_env("${MAMEPATH}\\MAMEControlConfig.exe"),
        "MAMEControlConfig.py",
        "MAMEControlConfig.exe"
    }
    
    for _, path in pairs(paths_to_check) do
        local file = io.open(path, "r")
        if file then
            file:close()
            config.preview_app_path = path
            debug_print("Found preview app at: " .. path)
            return true
        end
    end
    
    debug_print("Could not find preview application!")
    return false
end

-- Track whether preview is currently displayed
local preview_active = false
local last_pause_state = false
local current_rom = ""

-- Helper function to get current ROM name (handles different MAME versions)
local function get_rom_name()
    -- Try different ways to access the ROM name
    local rom_name = ""
    
    -- Method 1: Direct machine access
    if manager and manager.machine then
        -- Try as method first
        if type(manager.machine) == "function" then
            local machine = manager.machine()
            if machine and machine.system then
                if type(machine.system) == "function" then
                    local system = machine:system()
                    if system and system.name then
                        rom_name = system.name
                    end
                elseif type(machine.system) == "table" then
                    if machine.system.name then
                        rom_name = machine.system.name
                    end
                end
            end
        -- Then try as property
        elseif type(manager.machine) == "table" then
            if manager.machine.system then
                if type(manager.machine.system) == "function" then
                    local system = manager.machine:system()
                    if system and system.name then
                        rom_name = system.name
                    end
                elseif type(manager.machine.system) == "table" then
                    if manager.machine.system.name then
                        rom_name = manager.machine.system.name
                    end
                end
            end
        end
    end
    
    -- Method 2: Fallback using emu
    if rom_name == "" and emu then
        if emu.romname then
            rom_name = emu.romname()
        elseif emu.gamename then
            rom_name = emu.gamename()
        end
    end
    
    if rom_name == "" then
        debug_print("WARNING: Could not determine ROM name, using 'unknown'")
        rom_name = "unknown"
    end
    
    return rom_name
end

-- Helper function to check if game is paused
local function is_game_paused()
    -- Try different ways to check pause state
    local paused = false
    
    -- Method 1: Direct machine access
    if manager and manager.machine then
        -- Try as method first
        if type(manager.machine) == "function" then
            local machine = manager.machine()
            if machine and machine.paused then
                if type(machine.paused) == "function" then
                    paused = machine:paused()
                else
                    paused = machine.paused
                end
            end
        -- Then try as property
        elseif type(manager.machine) == "table" then
            if manager.machine.paused then
                if type(manager.machine.paused) == "function" then
                    paused = manager.machine:paused()
                else
                    paused = manager.machine.paused
                end
            end
        end
    end
    
    -- Method 2: Fallback
    if emu and emu.pause and type(emu.pause) == "function" then
        -- In some versions, emu.pause() returns current pause state
        paused = emu.pause()
    end
    
    return paused
end

-- Launch preview application
local function launch_preview(rom_name)
    if preview_active then
        debug_print("Preview already active")
        return
    end
    
    if not config.preview_app_path or config.preview_app_path == "" then
        if not find_preview_app_path() then
            debug_print("Error: Preview application not found")
            return
        end
    end
    
    local is_python_script = config.preview_app_path:match("%.py$")
    local cmd
    
    if is_python_script then
        cmd = string.format('%s "%s" --preview-only --game %s --screen %d', 
                           config.python_exe, config.preview_app_path, rom_name, config.screen)
        if config.auto_close then
            cmd = cmd .. " --auto-close"
        end
    else
        cmd = string.format('"%s" --preview-only --game %s --screen %d', 
                           config.preview_app_path, rom_name, config.screen)
        if config.auto_close then
            cmd = cmd .. " --auto-close"
        end
    end
    
    debug_print("Executing: " .. cmd)
    
    -- Use os.execute for Windows or emu.system for cross-platform
    if emu and emu.system then
        emu.system(cmd)
    else
        os.execute("start " .. cmd)
    end
    
    preview_active = true
    debug_print("Preview launched for " .. rom_name)
end

-- Close preview application
local function close_preview()
    if not preview_active then
        return
    end
    
    -- On Windows, try to find and kill the preview process
    if emu and emu.system then
        emu.system("taskkill /F /IM MAMEControlConfig.exe 2>nul")
        emu.system("taskkill /F /IM python.exe /FI \"WINDOWTITLE eq Control Preview*\" 2>nul")
    else
        os.execute("taskkill /F /IM MAMEControlConfig.exe 2>nul")
        os.execute("taskkill /F /IM python.exe /FI \"WINDOWTITLE eq Control Preview*\" 2>nul")
    end
    
    preview_active = false
    debug_print("Preview closed")
end

-- Set up the plugin
function exports.startplugin()
    -- Get ROM name using compatible method
    current_rom = get_rom_name()
    debug_print("MAME Preview Control Plugin loaded for " .. current_rom)
    
    -- Add UI menu item if supported
    if emu and emu.add_menu then
        local menu = {}
        menu[1] = {
            "Show Control Preview", 
            function() 
                launch_preview(current_rom)
                return true
            end
        }
        menu[2] = {
            "Hide Control Preview", 
            function()
                close_preview()
                return true
            end
        }
        emu.add_menu("Preview Controls", menu)
    end
    
    -- Hook into frame callbacks if supported
    if emu and emu.register_frame_done then
        emu.register_frame_done(function()
            -- Check if game is paused
            local is_paused = is_game_paused()
            
            -- Only trigger on pause state change
            if is_paused ~= last_pause_state then
                last_pause_state = is_paused
                
                if is_paused then
                    -- Game was just paused, show preview
                    debug_print("Game paused, showing preview")
                    launch_preview(current_rom)
                elseif config.auto_close then
                    -- Game was just unpaused, hide preview if auto-close is enabled
                    debug_print("Game unpaused, hiding preview")
                    close_preview()
                end
            end
        end)
    end
    
    -- Clean up when MAME exits
    if emu and emu.register_stop then
        emu.register_stop(function()
            close_preview()
        end)
    end
    
    -- Register a key handler for manual toggling with P key
    if emu and emu.register_frame then
        emu.register_frame(function()
            if emu.keypost and emu.keypost(input_device_item.KEYCODE_P) > 0 then
                debug_print("P key pressed, toggling preview")
                if preview_active then
                    close_preview()
                else
                    launch_preview(current_rom)
                end
            end
        end)
    end
end

-- Make sure we return the exports
return exports