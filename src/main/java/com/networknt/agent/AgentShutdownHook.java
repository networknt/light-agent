package com.networknt.agent;

import com.networknt.server.ShutdownHookProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Agent shutdown hook implementation to clean up resources.
 */
public class AgentShutdownHook implements ShutdownHookProvider {
    private static final Logger logger = LoggerFactory.getLogger(AgentShutdownHook.class);

    @Override
    public void onShutdown() {
        logger.info("AgentShutdownHook is called");
    }

}
