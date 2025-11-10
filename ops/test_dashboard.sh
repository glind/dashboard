#!/bin/bash

# Test script for dashboard functionality
# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Dashboard Test Suite${NC}"
echo "========================"

# Test 1: Stop any running instance
echo -e "\n${BLUE}Test 1: Cleaning up any running instances...${NC}"
./ops/startup.sh stop
sleep 2

# Test 2: Start dashboard
echo -e "\n${BLUE}Test 2: Starting dashboard...${NC}"
./ops/startup.sh start

# Test 3: Check status
echo -e "\n${BLUE}Test 3: Checking status...${NC}"
./ops/startup.sh status

# Test 4: Test API endpoints
echo -e "\n${BLUE}Test 4: Testing API endpoints...${NC}"

# Test root endpoint
echo -e "${BLUE}   Testing root endpoint...${NC}"
if curl -s "http://localhost:8008" > /dev/null; then
    echo -e "${GREEN}   ✅ Root endpoint working${NC}"
else
    echo -e "${RED}   ❌ Root endpoint failed${NC}"
fi

# Test API docs
echo -e "${BLUE}   Testing API docs...${NC}"
if curl -s "http://localhost:8008/docs" > /dev/null; then
    echo -e "${GREEN}   ✅ API docs working${NC}"
else
    echo -e "${RED}   ❌ API docs failed${NC}"
fi

# Test data endpoint
echo -e "${BLUE}   Testing data collection endpoint...${NC}"
if curl -s "http://localhost:8008/api/data/collect" > /dev/null; then
    echo -e "${GREEN}   ✅ Data collection endpoint working${NC}"
else
    echo -e "${RED}   ❌ Data collection endpoint failed${NC}"
fi

# Test 5: Show recent logs
echo -e "\n${BLUE}Test 5: Recent logs...${NC}"
./ops/startup.sh logs 5

echo -e "\n${GREEN}✅ Test suite completed!${NC}"
echo -e "${BLUE}💡 Dashboard should be running at: http://localhost:8008${NC}"