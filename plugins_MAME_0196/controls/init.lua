-- license:MIT
-- copyright-holders:Custom
-- MAME Controls Menu Plugin for MAME 0.196
local exports = {}
exports.name = "controls"
exports.version = "0.1.196"
exports.description = "MAME Controls Display Menu"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    local controls_shown = false
    local rom_detected = false
    local show_delay = 1  -- Reduced to ~1/6 second for quicker display
    local delay_counter = 0
    
    local function show_controls()
        if controls_shown then return end
        
        local game_name = emu.romname()
        print("Game: " .. (game_name or "nil"))
        
        if game_name and game_name ~= "" then
            -- Pause MAME
            emu.pause()
            print("Paused MAME")
            
            -- Show controls
            local command = string.format('pythonw "MAME Controls.pyw" --preview-only --game %s --screen 1', game_name)
            print("Running: " .. command)
            os.execute(command)
            controls_shown = true
            
            -- Unpause MAME
            emu.unpause()
            print("Unpaused MAME")
            
            -- Show a quick message
            if manager and manager.machine and manager.machine.popmessage then
                manager.machine:popmessage("Controls shown")
            end
        end
    end
    
    -- Menu population function - follows exact cheat plugin structure
    local function menu_populate()
        local menu = {}
        menu[1] = {"Show Controls", "", 0}  -- Format: [label, value, flags]
        return menu
    end
    
    -- Menu callback - follows exact cheat plugin structure
    local function menu_callback(index, event)
        if event == "select" then
            -- Reset to allow showing again
            controls_shown = false
            show_controls()
            return true
        end
        return false
    end
    
    -- Register menu exactly like the cheat plugin does
    emu.register_menu(menu_callback, menu_populate, "Controls")
    
    -- Using frame handler for ROM detection with minimal delay
    emu.register_frame(function()
        local game_name = emu.romname()
        
        -- Check if we have a valid ROM
        if game_name and game_name ~= "" and game_name ~= "___empty" then
            -- ROM is now detected
            if not rom_detected then
                rom_detected = true
                delay_counter = 0
                print("ROM detected: " .. game_name)
            end
            
            -- If ROM is detected but controls not shown yet, start the delay counter
            if rom_detected and not controls_shown then
                delay_counter = delay_counter + 1
                
                -- Show controls after minimal delay
                if delay_counter >= show_delay then
                    show_controls()
                end
            end
        else
            -- No ROM detected, reset flags
            rom_detected = false
            delay_counter = 0
        end
    end)
    
    -- Register start callback as an alternative way to detect ROM loading
    emu.register_start(function()
        -- This gets called when a ROM starts loading
        print("ROM start detected")
        rom_detected = true
        delay_counter = 0
        
        -- We'll still use the frame handler to show controls after a minimal delay
    end)
    
    -- Reset when game stops
    emu.register_stop(function()
        controls_shown = false
        rom_detected = false
        delay_counter = 0
        print("Controls plugin reset for next game")
    end)
    
    print("Controls plugin loaded (menu + immediate ROM detection)")
end

return exports