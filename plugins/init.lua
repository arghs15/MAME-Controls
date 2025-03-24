-- MAME Controls Menu Plugin with F9 hotkey
local exports = {}
exports.name = "mame_controls"
exports.version = "0.1"
exports.description = "MAME Controls Display"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    -- Variables to track key state
    local f9_pressed = false

    -- Function to show controls
    local function show_controls()
        -- Get the ROM name
        local game_name = emu.romname()

        -- Only proceed if we have a valid game name
        if game_name and game_name ~= "" and game_name ~= "___empty" then
            -- Pause MAME if the function exists
            if emu.pause then
                emu.pause()
            end
            
            -- Run the controls viewer
            local command = string.format('pythonw "MAME Controls.pyw" --preview-only --game %s --screen 1', game_name)
            os.execute(command)
            
            -- Unpause MAME if the function exists
            if emu.unpause then
                emu.unpause()
            end
        end
    end

    -- Simple menu with one option
    local function make_menu()
        local menu = {}
        menu[1] = {"Show Controls (F9)", "", 0}
        return menu
    end

    -- Menu callback function - handles menu selections
    local function menu_callback(index, event)
        if event == "select" then
            show_controls()
            return true
        end
        return false
    end

    -- Add frame done callback to check for F9 key
    emu.register_frame_done(function()
        -- Only check if we have necessary components
        if not manager or not manager.machine then
            return false
        end
        
        local machine = manager.machine
        if not machine.input then
            return false
        end
        
        -- Get the input manager
        local input = machine.input
        
        -- Try to get the F9 key state
        local key_state = false
        if input.seq_pressed then
            -- Create a sequence for F9 key
            local seq = input:seq_from_tokens("KEYCODE_F9")
            if seq then
                key_state = input:seq_pressed(seq)
            end
        end
        
        -- Detect rising edge (key just pressed)
        if key_state and not f9_pressed then
            show_controls()
        end
        
        -- Update pressed state
        f9_pressed = key_state
        
        return false  -- Keep the callback active
    end)

    -- Register our menu with MAME
    emu.register_menu(menu_callback, make_menu, "Controls")
end

return exports