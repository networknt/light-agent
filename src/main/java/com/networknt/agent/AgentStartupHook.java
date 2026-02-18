package com.networknt.agent;
import com.networknt.server.StartupHookProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Agent startup hook implementation to initialize resources.
 */
public class AgentStartupHook implements StartupHookProvider {
    private static final Logger logger = LoggerFactory.getLogger(AgentStartupHook.class);

    @Override
    public void onStartup() {
        logger.info("AgentStartupHook is started");
    }

}
