"""The demo corpus: eighteen research notes on autonomous port logistics.

Every company, person and product is fictional; the cities are real. The notes overlap on
purpose (the same companies appear in several of them, sometimes under a short name), so the
graph shows entity resolution, shared neighbours and communities that cut across documents.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Note:
    slug: str
    title: str
    body: str


NOTES: tuple[Note, ...] = (
    Note(
        "helios-robotics-profile",
        "Helios Robotics: company profile",
        """# Helios Robotics

## Overview

Helios Robotics Inc builds autonomous vehicles for container terminals. Helios Robotics was founded by Dr. Mira Okafor and Daniel Reyes in 2018. Mira Okafor serves as CEO of Helios Robotics, and Daniel Reyes is the CTO. Helios Robotics is headquartered in Rotterdam.

## Products

Helios launched the Atlas Platform in 2021. The Atlas Platform is powered by the Orion Engine, a navigation stack that combines sensor fusion with computer vision. Helios also develops the Atlas Charger, a docking unit for battery swaps.

## Growth

Tidewater Capital led the Series B round in Helios Robotics in 2023. Carlos Mendes, a partner at Tidewater Capital, took a seat on the Helios board. In 2024 Helios acquired Northgate Sensors and partnered with Voltaic Cells to secure battery supply. Helios employs about 340 people across Rotterdam and Gothenburg.""",
    ),
    Note(
        "atlas-platform-brief",
        "Atlas Platform and the Orion Engine",
        """# Atlas Platform technical brief

## Architecture

The Atlas Platform is a fleet of autonomous container carriers developed by Helios Robotics. Each carrier uses the Orion Engine for navigation. The Orion Engine fuses lidar, radar and camera data through sensor fusion, then plans routes with reinforcement learning.

## Sensors and power

Northgate Sensors supplies Helios Robotics with the lidar units used on every Atlas carrier. Voltaic Cells supplies Helios Robotics with the solid-state battery packs that power the fleet. A carrier runs a full shift on one charge, and the Atlas Charger swaps a pack in under four minutes.

## Fleet operations

Kestrel Analytics built the Harbor Twin, a digital twin that mirrors the terminal in real time. Daniel Reyes explained that Helios feeds every carrier trace into the Harbor Twin to support predictive maintenance. The Atlas Platform is deployed in Rotterdam and Antwerp.""",
    ),
    Note(
        "northgate-acquisition",
        "Helios acquires Northgate Sensors",
        """# Helios acquires Northgate Sensors

Helios Robotics announced in March 2024 that it acquired Northgate Sensors, a lidar maker based in Gothenburg. Northgate Sensors was founded in 2015 by Elin Sandberg, who remains CEO of Northgate Sensors after the deal. Prof. Henrik Lindgren, a professor at Gothenburg Institute of Technology, advises Northgate on sensor design.

## Why the deal matters

Mira Okafor said the acquisition secures the lidar supply for the Atlas Platform. Northgate Sensors previously supplied lidar to Meridian Port Systems, and that contract continues. Meridian Port Systems competes with Helios Robotics in the terminal automation market.

## Terms

Tidewater Capital funded the acquisition through a follow-on investment in Helios Robotics. Helios keeps the Northgate team in Gothenburg and opened a research lab there in 2025.""",
    ),
    Note(
        "voltaic-cells-batteries",
        "Voltaic Cells and solid-state batteries",
        """# Voltaic Cells and solid-state batteries

## The company

Voltaic Cells Inc is a battery maker based in Austin. Voltaic Cells develops the V3 Pack, a solid-state battery pack for heavy vehicles. Voltaic Cells was founded by Rachel Kim in 2016, and Rachel Kim serves as CEO.

## Customers

Voltaic Cells supplies Helios Robotics with the V3 Pack for the Atlas Platform. Lumen Energy, a grid storage company in Hamburg, partnered with Voltaic Cells to recycle used packs. Tidewater Capital invested in Voltaic Cells in 2022.

## Technology

A solid-state battery replaces the liquid electrolyte with a solid one, which raises energy density and removes the fire risk of liquid cells. Battery recycling is central to the partnership with Lumen Energy, because recovered lithium lowers the cost of every new pack. Carlos Mendes said Tidewater Capital sees solid-state battery supply as the bottleneck for port automation.""",
    ),
    Note(
        "tidewater-portfolio",
        "Tidewater Capital: port technology portfolio",
        """# Tidewater Capital portfolio

Tidewater Capital is a venture firm based in London that focuses on logistics technology. Carlos Mendes is a partner at Tidewater Capital and leads its port technology investments.

## Holdings

Tidewater Capital invested in Helios Robotics, Voltaic Cells and Kestrel Analytics. The firm led the Series B round in Helios Robotics in 2023 and funded the Northgate acquisition. Tidewater Capital also backed Aurora Cold Chain, a refrigerated logistics company in Antwerp.

## Thesis

Carlos Mendes argues that supply chain visibility and automation will converge. He believes a digital twin of the terminal, fed by autonomous vehicles, is the foundation for predictive maintenance and cold chain reliability. Carlos Mendes presented this thesis at the Global Logistics Summit in Rotterdam.""",
    ),
    Note(
        "europort-safety-rules",
        "EuroPort Safety Commission and autonomous carriers",
        """# EuroPort Safety Commission

## Mandate

The EuroPort Safety Commission regulates autonomous vehicles in European container terminals. Amara Nwosu chairs the EuroPort Safety Commission. The commission is based in Brussels.

## Approvals

The EuroPort Safety Commission approved the Atlas Platform in 2022 after a pilot in Rotterdam. The commission requires redundant sensors, so Helios Robotics added a second lidar from Northgate Sensors. The Port of Rotterdam Authority supported the pilot and shared incident data with the commission.

## Open questions

Amara Nwosu said the commission will review battery safety next. Solid-state battery packs from Voltaic Cells are the first technology under review. The Port Safety Symposium in Brussels will discuss the findings.""",
    ),
    Note(
        "meridian-singapore",
        "Meridian Port Systems and the Singapore market",
        """# Meridian Port Systems

Meridian Port Systems is a terminal automation company based in Singapore. Arjun Mehta founded Meridian Port Systems in 2017 and serves as CEO. Meridian develops the Meridian Hauler, an autonomous yard truck.

## Competition

Meridian Port Systems competes with Helios Robotics for terminal contracts. Meridian buys lidar from Northgate Sensors, which is now owned by Helios. Arjun Mehta said Meridian will qualify a second lidar supplier.

## The Singapore market

The Singapore Maritime Council hosts the Asia Port Automation Forum each year. Meridian Port Systems partnered with Pacific Harbor Alliance, a consortium of Asian terminal operators, to deploy the Meridian Hauler in Singapore. Pacific Harbor Alliance is headquartered in Singapore.""",
    ),
    Note(
        "kestrel-harbor-twin",
        "Kestrel Analytics and the Harbor Twin",
        """# Kestrel Analytics

Kestrel Analytics is a software company in Hamburg. Priya Nair is the CTO of Kestrel Analytics. Kestrel developed the Harbor Twin, a digital twin platform for container terminals.

## Integrations

The Harbor Twin integrates with the Atlas Platform and with the Orion Engine. Kestrel Analytics partnered with Helios Robotics in 2023. Baltic Freight Group, a shipping company in Hamburg, uses the Harbor Twin to plan berth schedules.

## Predictive maintenance

Priya Nair explained that the Harbor Twin applies machine learning to vehicle traces to forecast failures. Predictive maintenance cut unplanned downtime at Baltic Freight Group by a fifth. Tidewater Capital invested in Kestrel Analytics in 2022.""",
    ),
    Note(
        "global-logistics-summit-2025",
        "Global Logistics Summit 2025 report",
        """# Global Logistics Summit 2025

The Port of Rotterdam Authority hosted the Global Logistics Summit in Rotterdam in May 2025. Laura Becker, a director at the Port of Rotterdam Authority, opened the summit.

## Keynotes

Mira Okafor spoke at the Global Logistics Summit and presented the Atlas Platform roadmap. Arjun Mehta attended the Global Logistics Summit and described the Singapore deployment of the Meridian Hauler. Carlos Mendes moderated a panel at the Global Logistics Summit on supply chain automation.

## Announcements

Helios Robotics announced a partnership with Aurora Cold Chain at the summit. Kestrel Analytics unveiled a new release of the Harbor Twin. The EuroPort Safety Commission confirmed that Amara Nwosu would open the Port Safety Symposium in Brussels.""",
    ),
    Note(
        "aurora-cold-chain-pilot",
        "Aurora Cold Chain pilot in Antwerp",
        """# Aurora Cold Chain pilot

Aurora Cold Chain is a refrigerated logistics company based in Antwerp. Tomas Novak is head of operations at Aurora Cold Chain.

## The pilot

Aurora Cold Chain partnered with Helios Robotics to run the Atlas Platform in its Antwerp terminal. The pilot moves refrigerated containers between the quay and the cold store. Tomas Novak said cold chain reliability improved because the Harbor Twin predicts compressor failures.

## Investors and partners

Tidewater Capital backed Aurora Cold Chain in 2024. Lumen Energy supplies renewable energy to the Aurora cold stores. Aurora Cold Chain joined Pacific Harbor Alliance as an associate member.""",
    ),
    Note(
        "predictive-maintenance-note",
        "Predictive maintenance in container terminals",
        """# Predictive maintenance

Predictive maintenance uses sensor data to forecast equipment failures before they happen. In container terminals the data comes from lidar, motor controllers and battery management systems.

## Methods

Kestrel Analytics applies machine learning to vehicle traces in the Harbor Twin. Helios Robotics trains models on carrier data with federated learning, so each terminal keeps its data local. Federated learning lets Helios improve the Orion Engine without moving raw traces.

## Impact

Baltic Freight Group reported a lower rate of unplanned stops after adopting the Harbor Twin. Aurora Cold Chain uses predictive maintenance to protect cold chain integrity. Daniel Reyes said predictive maintenance is the strongest argument for connecting vehicles to a digital twin.""",
    ),
    Note(
        "asia-port-automation-forum",
        "Asia Port Automation Forum notes",
        """# Asia Port Automation Forum

The Singapore Maritime Council hosted the Asia Port Automation Forum in Singapore. Arjun Mehta presented the Meridian Hauler, and Priya Nair presented the Harbor Twin.

## Themes

Speakers focused on warehouse automation, sensor fusion and the supply chain impact of automated terminals. Pacific Harbor Alliance announced a pilot with Meridian Port Systems. Lumen Energy presented its battery recycling programme with Voltaic Cells.

## Takeaways

Delegates agreed that standards for autonomous yard vehicles are fragmented. The EuroPort Safety Commission was cited as the reference regulator, and Amara Nwosu joined a panel by video link.""",
    ),
    Note(
        "rotterdam-automation-roadmap",
        "Port of Rotterdam Authority: automation roadmap",
        """# Rotterdam automation roadmap

The Port of Rotterdam Authority manages the port of Rotterdam and sets its automation roadmap. Laura Becker leads the roadmap programme.

## Priorities

The authority supported the Atlas Platform pilot with Helios Robotics and shared incident data with the EuroPort Safety Commission. It plans to connect every terminal to a shared digital twin. Kestrel Analytics won the contract to extend the Harbor Twin across the port.

## Energy

Lumen Energy will supply renewable energy for charging autonomous vehicles in Rotterdam. The authority hosted the Global Logistics Summit to present the plan. Laura Becker said predictive maintenance and renewable energy are the two pillars of the roadmap.""",
    ),
    Note(
        "gothenburg-sensor-fusion",
        "Gothenburg research on sensor fusion",
        """# Sensor fusion research in Gothenburg

Prof. Henrik Lindgren is a professor at Gothenburg Institute of Technology and heads a research group there. The group studies sensor fusion for lidar and radar in harsh weather.

## Collaboration

Henrik Lindgren advises Northgate Sensors and collaborates with Helios Robotics. The group published a paper on sensor fusion that informed the Orion Engine. Northgate Sensors funds two doctoral students in the group.

## Findings

The group found that fusing lidar and radar halves false stops in fog. Helios Robotics adopted the method in the Orion Engine, and Meridian Port Systems asked Northgate Sensors for the same firmware. Computer vision adds a third channel that improves detection of cargo handlers on the quay.""",
    ),
    Note(
        "lumen-energy-profile",
        "Lumen Energy: company profile",
        """# Lumen Energy

Lumen Energy is a grid storage and renewable energy company based in Hamburg. Ingrid Vogel founded Lumen Energy in 2017 and serves as CEO. Nordic Grid Fund invested in Lumen Energy in 2021.

## Customers and partners

Lumen Energy supplies renewable energy to the Port of Rotterdam Authority and to Aurora Cold Chain. Lumen Energy partnered with Voltaic Cells to recycle used battery packs, and with Baltic Freight Group to power its Hamburg yard. Ingrid Vogel presented the battery recycling programme at the Asia Port Automation Forum.

## Outlook

Ingrid Vogel said grid storage will decide how fast ports can electrify. Lumen Energy competes with Harbor Grid Services for terminal energy contracts.""",
    ),
    Note(
        "baltic-freight-profile",
        "Baltic Freight Group: company profile",
        """# Baltic Freight Group

Baltic Freight Group is a shipping company based in Hamburg. Jonas Weber is the CEO of Baltic Freight Group. The company runs container services between Hamburg, Gothenburg and Tallinn.

## Technology

Baltic Freight Group uses the Harbor Twin to plan berth schedules. Baltic Freight Group partnered with Kestrel Analytics in 2023 and acquired Delta Freight Cooperative in 2024. Jonas Weber attended the Global Logistics Summit and the Baltic Logistics Forum.

## Events

Baltic Freight Group hosted the Baltic Logistics Forum in Tallinn. Priya Nair presented the Harbor Twin at the Baltic Logistics Forum, and Laura Becker spoke about the Rotterdam automation roadmap.""",
    ),
    Note(
        "pacific-harbor-profile",
        "Pacific Harbor Alliance: profile",
        """# Pacific Harbor Alliance

Pacific Harbor Alliance is a consortium of Asian terminal operators headquartered in Singapore. Dr. Wei Zhang chairs Pacific Harbor Alliance.

## Members and projects

Aurora Cold Chain joined Pacific Harbor Alliance as an associate member. Pacific Harbor Alliance partnered with Meridian Port Systems to deploy the Meridian Hauler in Singapore and Shanghai. Pacific Harbor Alliance also works with Fjord Intelligence Lab on autonomous navigation.

## Standards

Wei Zhang attended the Asia Port Automation Forum and argued that standards for autonomous yard vehicles should follow the EuroPort Safety Commission. Pacific Harbor Alliance competes with the Singapore Maritime Council for influence over regional standards.""",
    ),
    Note(
        "fjord-intelligence-lab",
        "Fjord Intelligence Lab",
        """# Fjord Intelligence Lab

Fjord Intelligence Lab is an AI research lab based in Oslo. Sigrid Haugen founded Fjord Intelligence Lab in 2020 as a spin-out of Gothenburg Institute of Technology. Prof. Henrik Lindgren advises Fjord Intelligence Lab.

## Research

Fjord Intelligence Lab develops the Fjord Navigator, a path planning model built on reinforcement learning and sensor fusion. Meridian Port Systems licensed the Fjord Navigator for the Meridian Hauler. Tidewater Capital invested in Fjord Intelligence Lab in 2024.

## Collaboration

Sigrid Haugen presented the Fjord Navigator at the Asia Port Automation Forum. Fjord Intelligence Lab partnered with Pacific Harbor Alliance on autonomous navigation, and with Northgate Sensors on lidar calibration.""",
    ),
)

# Questions replayed by the seeder so the playground history and the traffic charts have a
# shape on a fresh stack: (mode, question).
QUESTIONS: tuple[tuple[str, str], ...] = (
    ("local", "Who founded Helios Robotics?"),
    ("local", "What does Northgate Sensors supply to the Atlas Platform?"),
    ("local", "Who is the CEO of Voltaic Cells?"),
    ("local", "Which companies has Tidewater Capital invested in?"),
    ("local", "What did the EuroPort Safety Commission approve?"),
    ("local", "Who competes with Helios Robotics?"),
    ("local", "Where is Kestrel Analytics based?"),
    ("local", "Who attended the Global Logistics Summit?"),
    ("local", "Which company built the Harbor Twin?"),
    ("local", "What is the Meridian Hauler?"),
    ("local", "Who founded Lumen Energy?"),
    ("local", "Who chairs Pacific Harbor Alliance?"),
    ("global", "What are the main themes across these documents?"),
    ("global", "How is predictive maintenance used in port terminals?"),
    ("global", "Which organizations shape autonomous port logistics?"),
    ("global", "How do batteries and energy fit into port automation?"),
    ("hybrid", "How does Helios Robotics depend on its suppliers and investors?"),
    ("hybrid", "What role does the Harbor Twin play in Rotterdam and Antwerp?"),
    ("hybrid", "How is sensor fusion connected to Northgate Sensors and Helios Robotics?"),
    ("hybrid", "What is the relationship between Helios Robotics and Meridian Port Systems?"),
    ("hybrid", "Who regulates autonomous carriers and what did they decide?"),
    ("hybrid", "How did Aurora Cold Chain adopt the Atlas Platform?"),
    ("hybrid", "What does Fjord Intelligence Lab contribute to port navigation?"),
    ("global", "Which research groups and investors support these companies?"),
)
