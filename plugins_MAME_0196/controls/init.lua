-- license:MIT
-- copyright-holders:Custom
-- MAME Controls Menu Plugin for MAME 0.196 - Optimized Version
local exports = {}
exports.name = "controls"
exports.version = "0.1.196"
exports.description = "MAME Controls Display Menu"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    -- Flag to track pause state
    local user_paused = false
    -- Cache the current game to avoid redundant calls
    local current_game = ""
    -- Path to the executable (pre-compute since this doesn't change)
    local exe_path = "preview\\MAME Controls.exe"
    
    local function show_controls()
        -- Get the ROM name only once per function call
        local game_name = emu.romname()
        
        if game_name and game_name ~= "" then
            -- Build command using string concatenation instead of sprintf (faster)
            local command = '"' .. exe_path .. '" --preview-only --game ' .. game_name .. ' --screen 1 --hide-joystick --hide-buttons'
            
            -- Execute the command
            os.execute(command)
            
            -- Unpause if needed
            if user_paused then
                emu.unpause()
                user_paused = false
            end
        end
    end
    
    -- Simplified menu population function
    local function menu_populate()
        return {{"Show Controls", "", 0}}
    end
    
    -- Simplified menu callback
    local function menu_callback(index, event)
        if event == "select" then
            show_controls()
            return true
        end
        return false
    end
    
    -- Register menu with minimal overhead
    emu.register_menu(menu_callback, menu_populate, "Controls")
    
    -- Register pause handler if available
    if emu.register_pause then
        emu.register_pause(function()
            if not user_paused then
                user_paused = true
                show_controls()
            else
                user_paused = false
            end
        end)
    end
    
    -- Minimal reset function
    emu.register_stop(function()
        user_paused = false
    end)
end

return exports