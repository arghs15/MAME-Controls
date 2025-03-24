-- Minimal MAME Controls launcher
local exports = {}
exports.name = "mame_controls"
exports.version = "0.1"
exports.description = "MAME Controls Launcher"
exports.license = "MIT"
exports.author = { name = "Custom Plugin" }

function exports.startplugin()
    -- Variables to track state
    local waiting_for_rom = false
    local check_counter = 0
    local max_checks = 300  -- Check for up to 5 seconds (at 60 fps)
    
    -- Create a log file for debugging
    local log_file = io.open("mame_controls_log.txt", "w")
    if log_file then
        log_file:write("Plugin started at " .. os.date() .. "\n")
        log_file:close()
    end
    
    -- Register to be notified when a game starts
    emu.register_start(function()
        waiting_for_rom = true
        check_counter = 0
        
        local log_file = io.open("mame_controls_log.txt", "a")
        if log_file then
            log_file:write("Game start detected at " .. os.date() .. "\n")
            log_file:close()
        end
    end)
    
    -- Check each frame to see if we have a valid ROM name
    emu.register_frame(function()
        if not waiting_for_rom then
            return
        end
        
        -- Increment our counter
        check_counter = check_counter + 1
        
        -- Only check every 10 frames to reduce overhead
        if check_counter % 10 == 0 then
            local rom_name = emu.romname()
            
            -- Log periodically for debugging
            if check_counter % 60 == 0 then
                local log_file = io.open("mame_controls_log.txt", "a")
                if log_file then
                    log_file:write("Check " .. check_counter .. ": ROM name = '" .. tostring(rom_name) .. "'\n")
                    log_file:close()
                end
            end
            
            -- Check if we have a valid ROM name
            if rom_name and rom_name ~= "" and rom_name ~= "___empty" then
                -- We have a valid ROM name, launch the preview
                local log_file = io.open("mame_controls_log.txt", "a")
                if log_file then
                    log_file:write("Valid ROM detected: " .. rom_name .. " at " .. os.date() .. "\n")
                    log_file:close()
                end
                
                -- Run with simple command (no manager:machine call)
                local command = string.format('python "MAME Controls.pyw" --preview-only --game %s --screen 2 --auto-close', rom_name)
                os.execute(command .. " &")
                
                -- Don't check anymore
                waiting_for_rom = false
            elseif check_counter >= max_checks then
                -- Give up after max_checks
                local log_file = io.open("mame_controls_log.txt", "a")
                if log_file then
                    log_file:write("Giving up after " .. check_counter .. " checks\n")
                    log_file:close()
                end
                
                waiting_for_rom = false
            end
        end
    end)
    
    -- Log completion of startup
    local log_file = io.open("mame_controls_log.txt", "a")
    if log_file then
        log_file:write("Plugin initialization complete\n")
        log_file:close()
    end
end

return exports