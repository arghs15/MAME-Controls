-- Unified MAME Controls Plugin with version detection
-- Simply calls the appropriate original script based on MAME version
local exports = {}
exports.name = "mame_controls"
exports.version = "0.3" -- Unified version
exports.description = "MAME Controls Display (Universal)"
exports.license = "MIT"
exports.author = { name = "Custom" }

function exports.startplugin()
    local is_old_mame = false
    local mame_version = 0
    
    -- Function to detect MAME version and available features
    local function detect_mame_version()
        -- Check if we can get MAME version
        if emu.app_version then
            local version_str = emu.app_version()
            print("MAME Version: " .. version_str)
            
            -- Extract version number 
            local major_version = tonumber(string.match(version_str, "(%d+)%."))
            local minor_version = tonumber(string.match(version_str, "%.(%d+)"))
            
            if major_version and minor_version then
                -- Convert to a comparable number (0.196 -> 196, etc.)
                mame_version = major_version * 1000 + minor_version
                print("Numeric version: " .. mame_version)
                
                -- Simple version check - if it's 0.196 or earlier, use old mode
                is_old_mame = (mame_version <= 196)
                print("Using old MAME compatibility mode: " .. tostring(is_old_mame))
            end
        else
            -- If emu.app_version doesn't exist, it's definitely an old version
            print("emu.app_version not available, assuming older MAME")
            is_old_mame = true
        end
    end
    
    -- Run the version detection
    detect_mame_version()
    
    -- Load and run the appropriate original script without modifications
    if is_old_mame then
        -- *** CODE FOR OLDER MAME (0.196) ***
        print("Running MAME 0.196 controls script")
        
        -- Flag to indicate when a pause was caused by the user
        local user_paused = false
        
        local function show_controls()
            local game_name = emu.romname()
            print("Game: " .. (game_name or "nil"))
            
            if game_name and game_name ~= "" then
                -- Show controls
                local command = string.format('pythonw "MAME Controls.pyw" --preview-only --game %s --screen 1 --hide-joystick --hide-buttons', game_name)
                print("Running: " .. command)
                os.execute(command)
                
                -- Unpause MAME if it was paused by the user
                if user_paused then
                    print("Unpausing MAME after controls")
                    emu.unpause()
                    user_paused = false
                end
            end
        end
        
        -- Menu population function
        local function menu_populate()
            local menu = {}
            menu[1] = {"Show Controls", "", 0}
            return menu
        end
        
        -- Menu callback
        local function menu_callback(index, event)
            if event == "select" then
                show_controls()
                return true
            end
            return false
        end
        
        -- Register menu
        emu.register_menu(menu_callback, menu_populate, "Controls")
        
        -- Register pause handler
        if emu.register_pause then
            print("Registering pause handler")
            emu.register_pause(function()
                -- When the user pauses, set our flag and show controls
                if not user_paused then
                    user_paused = true
                    print("User paused MAME")
                    show_controls()
                else
                    -- Reset our flag when MAME is unpaused
                    user_paused = false
                    print("MAME unpaused")
                end
            end)
        else
            print("emu.register_pause not available in this MAME version")
        end
        
        -- Reset when game stops
        emu.register_stop(function()
            user_paused = false
            print("Controls plugin reset for next game")
        end)
        
        print("Controls plugin loaded (pause detection + menu only)")
        
    else
        -- *** CODE FOR NEWER MAME (0.275+) ***
        print("Running MAME 0.275+ controls script")
        
        -- Variables to track key state
        local f9_pressed = false
        
        -- Change these variables if you're changing the button combination
        local start_pressed = false  -- Tracks Start button
        local rb_pressed = false     -- Tracks Right Bumper (RB)

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
            -- Update this text if you change the button combination
            menu[1] = {"Show Controls (F9 or Start+RB)", "", 0}
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

        -- Add frame done callback to check for key combinations
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
            
            -- Check F9 key
            local f9_state = false
            if input.seq_pressed then
                -- Create a sequence for F9 key
                local seq = input:seq_from_tokens("KEYCODE_F9")
                if seq then
                    f9_state = input:seq_pressed(seq)
                end
            end
            
            -- ======= FIRST HOTKEY BUTTON =======
            -- Check Start button (CHANGE THIS SECTION FOR DIFFERENT BUTTON)
            local start_state = false
            if input.seq_pressed then
                -- Try multiple mappings for Start button
                local seq_start1 = input:seq_from_tokens("JOYCODE_1_BUTTON10")  -- Common mapping
                local seq_start2 = input:seq_from_tokens("JOYCODE_1_START")     -- Alternative mapping
                local seq_start3 = input:seq_from_tokens("JOYCODE_1_BUTTON12")  -- Another common mapping
                local seq_xinput = input:seq_from_tokens("XINPUT_1_START")      -- XInput mapping
                
                -- Check all possible mappings (replace these if using different buttons)
                if seq_start1 then start_state = start_state or input:seq_pressed(seq_start1) end
                if seq_start2 then start_state = start_state or input:seq_pressed(seq_start2) end
                if seq_start3 then start_state = start_state or input:seq_pressed(seq_start3) end
                if seq_xinput then start_state = start_state or input:seq_pressed(seq_xinput) end
            end
            
            -- ======= SECOND HOTKEY BUTTON =======
            -- Check RB button (CHANGE THIS SECTION FOR DIFFERENT BUTTON)
            local rb_state = false
            if input.seq_pressed then
                -- Try multiple mappings for RB button
                local seq_rb1 = input:seq_from_tokens("JOYCODE_1_BUTTON6")         -- Common mapping
                local seq_rb2 = input:seq_from_tokens("XINPUT_1_SHOULDER_R")       -- XInput mapping
                
                -- Check all possible mappings (replace these if using different buttons)
                if seq_rb1 then rb_state = rb_state or input:seq_pressed(seq_rb1) end
                if seq_rb2 then rb_state = rb_state or input:seq_pressed(seq_rb2) end
            end
            
            -- Detect F9 key press
            if f9_state and not f9_pressed then
                show_controls()
            end
            
            -- Detect button combination (only trigger when both are pressed)
            -- CHANGE THIS CONDITION IF USING DIFFERENT BUTTONS
            if start_state and rb_state and (not start_pressed or not rb_pressed) then
                show_controls()
            end
            
            -- Update pressed states
            f9_pressed = f9_state
            start_pressed = start_state
            rb_pressed = rb_state
            
            return false  -- Keep the callback active
        end)

        -- Register our menu with MAME
        emu.register_menu(menu_callback, make_menu, "Controls")
    end
    
    print("MAME Controls plugin loaded successfully")
end

return exports